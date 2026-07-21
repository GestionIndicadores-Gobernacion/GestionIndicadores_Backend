# app/modules/support/routes/support_routes.py
import logging
import smtplib
import threading

from flask import current_app, jsonify, request
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.core.extensions import limiter
from app.shared.models.user import User
from app.modules.support.models.ticket import TICKET_STATUSES
from app.modules.support.schemas.ticket_schema import (
    AddMessageSchema,
    CreateTicketSchema,
    SupportMessageSchema,
    SupportTicketDetailSchema,
    SupportTicketSummarySchema,
    UpdateTicketStatusSchema,
)
from app.modules.notifications.models.notification import CATEGORY_SUPPORT_REPLY
from app.modules.notifications.services.notification_handler import NotificationHandler
from app.modules.support.services.email_sender import (
    SmtpNotConfiguredError,
    send_support_report,
)
from app.modules.support.services.ticket_handler import TicketHandler

logger = logging.getLogger(__name__)

blp = Blueprint(
    "support", __name__,
    url_prefix="/support",
    description="Tickets de soporte y respuestas tipo chat",
)


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────
def _current_user() -> User | None:
    uid = get_jwt_identity()
    if uid is None:
        return None
    return User.query.get(int(uid))


def _is_admin(user: User | None) -> bool:
    return bool(user and user.role and user.role.name == "admin")


def _dispatch_support_email(**kwargs) -> None:
    """Envía el correo de soporte en un hilo con su propio app-context, para
    que la latencia de SMTP no bloquee la respuesta HTTP de creación."""
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            try:
                send_support_report(**kwargs)
            except SmtpNotConfiguredError:
                logger.warning("support: ticket %s creado, pero SMTP no configurado.", kwargs.get("ticket_id"))
            except smtplib.SMTPException:
                logger.exception("support: ticket %s: falló el envío SMTP.", kwargs.get("ticket_id"))
            except Exception:
                logger.exception("support: ticket %s: error inesperado enviando email.", kwargs.get("ticket_id"))

    threading.Thread(target=_run, daemon=True).start()


def _mark_ticket_read(user: User, ticket) -> None:
    """Marca el ticket como leído para quien lo consulta y sincroniza las
    notificaciones (campana) de ese ticket. Se usa tanto al abrir el detalle
    como en el polling incremental, para que ver el chat marque lo entrante."""
    if ticket.user_id == user.id:
        TicketHandler.mark_admin_replies_as_read(ticket)
    if _is_admin(user):
        TicketHandler.mark_user_messages_as_read_by_admin(ticket)
    NotificationHandler.mark_read_by_entity(
        user_id=user.id, category=CATEGORY_SUPPORT_REPLY, entity_id=ticket.id
    )


# ─────────────────────────────────────────────────────────────────────────
# Crear ticket + listar
# ─────────────────────────────────────────────────────────────────────────
@blp.route("/tickets")
class TicketCollection(MethodView):

    @jwt_required()
    def get(self):
        """Lista tickets — admin ve todos, usuario ve solo los suyos."""
        user = _current_user()
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        status = request.args.get("status") or None
        # `mine=true` fuerza "solo mis reportes" aunque sea admin. Lo usa el FAB
        # ("Mis reportes"), que es la vista personal; el panel admin (/support)
        # no lo manda y sigue viendo todos los tickets.
        mine_only = request.args.get("mine", "false").lower() == "true"

        if _is_admin(user) and not mine_only:
            tickets = TicketHandler.list_all(status=status)
        else:
            tickets = TicketHandler.list_for_user(user.id)
            if status and status in TICKET_STATUSES:
                tickets = [t for t in tickets if t.status == status]

        return jsonify(SupportTicketSummarySchema(many=True).dump(tickets)), 200

    # Rate-limit para evitar spam al crear tickets.
    @limiter.limit("5 per minute; 20 per hour")
    @jwt_required()
    @blp.arguments(CreateTicketSchema)
    def post(self, payload):
        user = _current_user()
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        message = payload["message"]
        current_url = payload.get("current_url", "") or ""
        user_agent = payload.get("user_agent", "") or ""
        screenshot = payload.get("screenshot_data_url")

        # Imágenes a persistir en el primer mensaje: la lista nueva + el
        # screenshot legado (si vino) al frente, sin duplicar.
        images = list(payload.get("images") or [])
        if screenshot and screenshot not in images:
            images.insert(0, screenshot)

        ticket = TicketHandler.create(
            user_id=user.id,
            message=message,
            current_url=current_url,
            user_agent=user_agent,
            images=images,
        )

        # Email al destinatario configurado, en un hilo aparte para NO
        # bloquear la respuesta con la latencia de SMTP (hasta 20s). Si falla
        # NO afecta a la creación — el ticket queda persistido y visible.
        full_name = f"{user.first_name} {user.last_name}".strip() or user.email
        role_name = user.role.name if user.role else "(sin rol)"
        _dispatch_support_email(
            reporter_name=full_name,
            reporter_email=user.email,
            reporter_role=role_name,
            message_text=message,
            current_url=current_url,
            user_agent=user_agent,
            screenshot_data_url=screenshot,
            ticket_id=ticket.id,
        )

        return jsonify(SupportTicketDetailSchema().dump(ticket)), 201


# ─────────────────────────────────────────────────────────────────────────
# Conteo de mensajes admin no leídos por el usuario actual
# ─────────────────────────────────────────────────────────────────────────
@blp.route("/tickets/unread-count")
class TicketUnreadCount(MethodView):

    @jwt_required()
    def get(self):
        """Badge del FAB (todos los roles): respuestas de admin sin leer en los
        tickets PROPIOS del usuario actual."""
        user = _current_user()
        if not user:
            return jsonify({"unread_count": 0}), 200
        count = TicketHandler.count_unread_for_user(user.id)
        return jsonify({"unread_count": count}), 200


@blp.route("/tickets/admin/unread-count")
class TicketAdminUnreadCount(MethodView):

    @jwt_required()
    def get(self):
        """Badge del panel de administración: tickets (no cerrados) con
        mensajes de usuario que ningún admin ha leído. Solo admins."""
        user = _current_user()
        if not _is_admin(user):
            return jsonify({"unread_count": 0}), 200
        return jsonify({"unread_count": TicketHandler.count_unread_for_admin()}), 200


# ─────────────────────────────────────────────────────────────────────────
# Detalle / cambio de estado de un ticket
# ─────────────────────────────────────────────────────────────────────────
@blp.route("/tickets/<int:ticket_id>")
class TicketItem(MethodView):

    @jwt_required()
    def get(self, ticket_id: int):
        user = _current_user()
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        ticket = TicketHandler.get(ticket_id)
        if not ticket:
            return jsonify({"error": "Ticket no encontrado"}), 404
        if ticket.user_id != user.id and not _is_admin(user):
            return jsonify({"error": "No tienes acceso a este ticket"}), 403

        # Abrir el ticket marca lo pendiente como leído (mensajes + campana),
        # manteniendo sincronizados los dos contadores de "no leído".
        _mark_ticket_read(user, ticket)

        return jsonify(SupportTicketDetailSchema().dump(ticket)), 200

    @jwt_required()
    @blp.arguments(UpdateTicketStatusSchema)
    def patch(self, payload, ticket_id: int):
        user = _current_user()
        if not _is_admin(user):
            return jsonify({"error": "Solo administradores pueden cambiar el estado."}), 403

        ticket = TicketHandler.get(ticket_id)
        if not ticket:
            return jsonify({"error": "Ticket no encontrado"}), 404

        updated, err = TicketHandler.update_status(ticket, payload["status"])
        if err:
            return jsonify({"error": err}), 400
        return jsonify(SupportTicketDetailSchema().dump(updated)), 200


# ─────────────────────────────────────────────────────────────────────────
# Añadir mensaje a un ticket (chat)
# ─────────────────────────────────────────────────────────────────────────
@blp.route("/tickets/<int:ticket_id>/messages")
class TicketMessages(MethodView):

    @jwt_required()
    def get(self, ticket_id: int):
        """Polling incremental: devuelve solo los mensajes con id > ?after=.
        Evita re-descargar el hilo completo (con imágenes) en cada sondeo."""
        user = _current_user()
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        ticket = TicketHandler.get(ticket_id)
        if not ticket:
            return jsonify({"error": "Ticket no encontrado"}), 404
        if ticket.user_id != user.id and not _is_admin(user):
            return jsonify({"error": "No tienes acceso a este ticket"}), 403

        try:
            after = int(request.args.get("after", 0) or 0)
        except (TypeError, ValueError):
            after = 0

        messages = TicketHandler.messages_after(ticket_id, after)
        # Ver el chat (polling con el ticket abierto) marca como leído lo que
        # va entrando, igual que abrir el detalle. Los helpers no hacen commit
        # si no hay nada pendiente, así que es barato.
        _mark_ticket_read(user, ticket)
        return jsonify({
            "status": ticket.status,
            "messages": SupportMessageSchema(many=True).dump(messages),
        }), 200

    @limiter.limit("30 per minute; 200 per hour")
    @jwt_required()
    @blp.arguments(AddMessageSchema)
    def post(self, payload, ticket_id: int):
        user = _current_user()
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        ticket = TicketHandler.get(ticket_id)
        if not ticket:
            return jsonify({"error": "Ticket no encontrado"}), 404

        if ticket.user_id != user.id and not _is_admin(user):
            return jsonify({"error": "No tienes acceso a este ticket"}), 403

        if ticket.status == "cerrado":
            return jsonify({"error": "El ticket está cerrado y no admite mensajes."}), 400

        # Combinamos la lista nueva con la imagen única (legado), sin duplicar.
        images = list(payload.get("images") or [])
        legacy = payload.get("image_data_url")
        if legacy and legacy not in images:
            images.insert(0, legacy)

        msg, err = TicketHandler.add_message(
            ticket=ticket,
            author=user,
            body=payload.get("body", ""),
            images=images,
        )
        if err:
            return jsonify({"error": err}), 400
        return jsonify(SupportMessageSchema().dump(msg)), 201
