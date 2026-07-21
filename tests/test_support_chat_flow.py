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
