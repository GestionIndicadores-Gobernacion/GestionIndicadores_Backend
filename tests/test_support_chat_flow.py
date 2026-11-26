"""Flujo del chat de soporte: notificaciones bidireccionales, unificación del
'no leído' entre campana y badge, reapertura de tickets y polling incremental.
"""
import pytest

from app.core.extensions import db


@pytest.fixture(autouse=True)
def _clean(app):
    """La BD es de sesión: limpiamos tickets/mensajes/notificaciones antes de
    cada test para que los conteos globales sean deterministas e independientes
    del orden de ejecución."""
    from app.modules.support.models.ticket import SupportTicket
    from app.modules.support.models.message import SupportMessage
    from app.modules.notifications.models.notification import Notification
    with app.app_context():
        Notification.query.delete()
        SupportMessage.query.delete()
        SupportTicket.query.delete()
        db.session.commit()
    yield


@pytest.fixture()
def _people(app):
    """Crea (idempotente) roles admin/viewer y tres usuarios: dueño, admin1, admin2."""
    from app.shared.models.role import Role
    from app.shared.models.user import User

    with app.app_context():
        admin_role = Role.query.filter_by(name="admin").first() or Role(name="admin", description="a")
        viewer_role = Role.query.filter_by(name="viewer").first() or Role(name="viewer", description="v")
        db.session.add_all([admin_role, viewer_role])
        db.session.flush()

        def mk(email, role):
            u = User.query.filter_by(email=email).first()
            if u is None:
                u = User(first_name="N", last_name="A", email=email, role_id=role.id)
                u.set_password("pw")
                db.session.add(u)
            return u

        owner = mk("owner@x.co", viewer_role)
        admin1 = mk("admin1@x.co", admin_role)
        admin2 = mk("admin2@x.co", admin_role)
        db.session.commit()
        return {"owner": owner.id, "admin1": admin1.id, "admin2": admin2.id}


def _unread_notifs(user_id, entity_id):
    from app.modules.notifications.models.notification import Notification
    return Notification.query.filter_by(
        user_id=user_id, entity_id=entity_id, category="support_reply", is_read=False
    ).count()


def test_full_support_flow(app, _people):
    from app.shared.models.user import User
    from app.modules.support.services.ticket_handler import TicketHandler
    from app.modules.notifications.services.notification_handler import NotificationHandler
    from app.modules.notifications.models.notification import CATEGORY_SUPPORT_REPLY

    owner_id, admin1_id, admin2_id = _people["owner"], _people["admin1"], _people["admin2"]

    with app.app_context():
        owner = User.query.get(owner_id)
        admin1 = User.query.get(admin1_id)

        # 1) Crear ticket → ambos admins reciben notificación; badge admin = 1.
        ticket = TicketHandler.create(user_id=owner_id, message="No carga el dashboard")
        assert _unread_notifs(admin1_id, ticket.id) == 1
        assert _unread_notifs(admin2_id, ticket.id) == 1
        assert TicketHandler.count_unread_for_admin() == 1
        assert TicketHandler.count_unread_for_user(owner_id) == 0

        # 2) Admin abre el ticket → se limpia su badge y su notificación.
        TicketHandler.mark_user_messages_as_read_by_admin(ticket)
        NotificationHandler.mark_read_by_entity(admin1_id, CATEGORY_SUPPORT_REPLY, ticket.id)
        assert _unread_notifs(admin1_id, ticket.id) == 0
        assert TicketHandler.count_unread_for_admin() == 0  # ya no quedan usuarios sin leer

        # 3) Admin responde → el dueño recibe notificación y badge = 1.
        TicketHandler.add_message(ticket=ticket, author=admin1, body="Ya lo revisamos")
        assert ticket.status == "en_proceso"          # pendiente → en_proceso
        assert TicketHandler.count_unread_for_user(owner_id) == 1
        assert _unread_notifs(owner_id, ticket.id) == 1

        # 4) Dueño abre el ticket → se limpian SUS dos contadores a la vez.
        TicketHandler.mark_admin_replies_as_read(ticket)
        NotificationHandler.mark_read_by_entity(owner_id, CATEGORY_SUPPORT_REPLY, ticket.id)
        assert TicketHandler.count_unread_for_user(owner_id) == 0
        assert _unread_notifs(owner_id, ticket.id) == 0

        # 5) Admin marca resuelto y el USUARIO responde → reabre + avisa admins.
        TicketHandler.update_status(ticket, "resuelto")
        TicketHandler.add_message(ticket=ticket, author=owner, body="Sigue igual")
        assert ticket.status == "en_proceso"          # resuelto → reabierto
        # admin1 ya participó → recibe aviso; el badge admin vuelve a 1.
        assert _unread_notifs(admin1_id, ticket.id) == 1
        assert TicketHandler.count_unread_for_admin() == 1

        # 6) Polling incremental: solo trae los mensajes nuevos.
        all_msgs = TicketHandler.messages_after(ticket.id, 0)
        assert len(all_msgs) == 3                      # inicial + admin + usuario
        after = TicketHandler.messages_after(ticket.id, all_msgs[1].id)
        assert len(after) == 1 and after[0].body == "Sigue igual"


def test_admin_reply_flags(app, _people):
    from app.shared.models.user import User
    from app.modules.support.services.ticket_handler import TicketHandler

    owner_id, admin1_id = _people["owner"], _people["admin1"]
    with app.app_context():
        admin1 = User.query.get(admin1_id)
        ticket = TicketHandler.create(user_id=owner_id, message="algo va mal aqui")
        msg, err = TicketHandler.add_message(ticket=ticket, author=admin1, body="respuesta")
        assert err is None
        # Mensaje admin nace leído por admin y sin leer por el dueño.
        assert msg.is_admin_reply is True
        assert msg.read_by_admin is True
        assert msg.read_by_owner is False


def _notifs(user_id, entity_id):
    from app.modules.notifications.models.notification import Notification
    return Notification.query.filter_by(
        user_id=user_id, entity_id=entity_id, category="support_reply"
    ).all()


def test_notifications_identify_author_and_ticket(app, _people):
    from app.shared.models.user import User
    from app.modules.support.services.ticket_handler import TicketHandler

    owner_id, admin1_id = _people["owner"], _people["admin1"]
    with app.app_context():
        owner = User.query.get(owner_id)
        owner.first_name, owner.last_name = "Ana", "Pérez"
        admin1 = User.query.get(admin1_id)
        ticket = TicketHandler.create(user_id=owner_id, message="Falla el login")

        # Ticket nuevo: el admin ve quién lo creó y el número.
        (n,) = _notifs(admin1_id, ticket.id)
        assert n.title == f"Nuevo reporte #{ticket.id} de Ana Pérez"

        TicketHandler.add_message(ticket=ticket, author=admin1, body="¿Qué navegador usas?")
        (n,) = _notifs(owner_id, ticket.id)
        assert n.title == f"Nueva respuesta de soporte en tu reporte #{ticket.id}"
        assert n.message == "¿Qué navegador usas?"

        TicketHandler.add_message(ticket=ticket, author=owner, body="Chrome")
        (n,) = [x for x in _notifs(admin1_id, ticket.id) if not x.is_read]
        assert n.title == f"Ana Pérez respondió en el reporte #{ticket.id}"


def test_no_duplicate_unread_notifications_per_ticket(app, _people):
    from app.shared.models.user import User
    from app.modules.support.services.ticket_handler import TicketHandler
    from app.modules.notifications.services.notification_handler import NotificationHandler
    from app.modules.notifications.models.notification import CATEGORY_SUPPORT_REPLY

    owner_id, admin1_id = _people["owner"], _people["admin1"]
    with app.app_context():
        owner = User.query.get(owner_id)
        admin1 = User.query.get(admin1_id)
        ticket = TicketHandler.create(user_id=owner_id, message="Error 500")

        # Tres respuestas seguidas del admin → UNA notificación no leída.
        for body in ("uno", "dos", "tres"):
            TicketHandler.add_message(ticket=ticket, author=admin1, body=body)
        assert _unread_notifs(owner_id, ticket.id) == 1
        (n,) = _notifs(owner_id, ticket.id)
        assert n.message == "3 mensajes nuevos · tres"
        assert NotificationHandler.count_unread(owner_id) == 1

        # El dueño la lee; una respuesta posterior genera un aviso NUEVO.
        TicketHandler.mark_admin_replies_as_read(ticket)
        NotificationHandler.mark_read_by_entity(owner_id, CATEGORY_SUPPORT_REPLY, ticket.id)
        assert NotificationHandler.count_unread(owner_id) == 0
        TicketHandler.add_message(ticket=ticket, author=admin1, body="cuatro")
        assert _unread_notifs(owner_id, ticket.id) == 1
        assert len(_notifs(owner_id, ticket.id)) == 2
        unread = [x for x in _notifs(owner_id, ticket.id) if not x.is_read][0]
        assert unread.message == "cuatro"

        # Lado admin: "nuevo reporte" + 2 mensajes del usuario → 1 aviso.
        TicketHandler.add_message(ticket=ticket, author=owner, body="a")
        TicketHandler.add_message(ticket=ticket, author=owner, body="b")
        assert _unread_notifs(admin1_id, ticket.id) == 1


def test_admin_owned_ticket_notifies_other_admins(app, _people):
    """Un admin que reporta un fallo actúa como usuario en SU ticket."""
    from app.shared.models.user import User
    from app.modules.support.services.ticket_handler import TicketHandler
    from app.modules.notifications.services.notification_handler import NotificationHandler
    from app.modules.notifications.models.notification import CATEGORY_SUPPORT_REPLY

    admin1_id, admin2_id = _people["admin1"], _people["admin2"]
    with app.app_context():
        admin1 = User.query.get(admin1_id)
        admin2 = User.query.get(admin2_id)
        ticket = TicketHandler.create(user_id=admin1_id, message="Reporte del admin 1")
        assert _unread_notifs(admin2_id, ticket.id) == 1
        assert _unread_notifs(admin1_id, ticket.id) == 0

        # admin2 lo atiende y responde → avisa al dueño (admin1).
        TicketHandler.mark_user_messages_as_read_by_admin(ticket)
        NotificationHandler.mark_read_by_entity(admin2_id, CATEGORY_SUPPORT_REPLY, ticket.id)
        msg, _ = TicketHandler.add_message(ticket=ticket, author=admin2, body="Lo reviso")
        assert msg.is_admin_reply is True
        assert _unread_notifs(admin1_id, ticket.id) == 1
        assert TicketHandler.count_unread_for_user(admin1_id) == 1

        # admin1 contesta en SU ticket → cuenta como mensaje de usuario y avisa a admin2.
        msg, _ = TicketHandler.add_message(ticket=ticket, author=admin1, body="Gracias, sigue")
        assert msg.is_admin_reply is False
        assert msg.read_by_admin is False
        assert _unread_notifs(admin2_id, ticket.id) == 1
        assert TicketHandler.count_unread_for_admin() == 1


def test_inactive_admin_participant_not_notified(app, _people):
    from app.shared.models.user import User
    from app.modules.support.services.ticket_handler import TicketHandler

    owner_id, admin1_id, admin2_id = _people["owner"], _people["admin1"], _people["admin2"]
    with app.app_context():
        owner = User.query.get(owner_id)
        admin1 = User.query.get(admin1_id)
        ticket = TicketHandler.create(user_id=owner_id, message="Ayuda")
        TicketHandler.add_message(ticket=ticket, author=admin1, body="Hola")

        admin1.is_active = False
        db.session.commit()
        try:
            before = len(_notifs(admin1_id, ticket.id))
            TicketHandler.add_message(ticket=ticket, author=owner, body="¿Sigues ahí?")
            # El único admin que participó está inactivo → se avisa a los activos.
            assert len(_notifs(admin1_id, ticket.id)) == before
            assert _unread_notifs(admin2_id, ticket.id) == 1
        finally:
            admin1.is_active = True
            db.session.commit()
