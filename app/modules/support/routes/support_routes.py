# app/modules/support/routes/support_routes.py
import logging
import smtplib

from flask import jsonify, request
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
        if _is_admin(user):
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

        # Email al destinatario configurado. Si falla NO tumbamos la
        # creación del ticket — el ticket queda persistido y el admin
        # podrá verlo igual desde el panel.
        try:
            full_name = f"{user.first_name} {user.last_name}".strip() or user.email
            role_name = user.role.name if user.role else "(sin rol)"
            send_support_report(
                reporter_name=full_name,
                reporter_email=user.email,
                reporter_role=role_name,
                message_text=message,
                current_url=current_url,
                user_agent=user_agent,
                screenshot_data_url=screenshot,
                ticket_id=ticket.id,
            )
        except SmtpNotConfiguredError:
            logger.warning("support: ticket %s creado, pero SMTP no configurado.", ticket.id)
        except smtplib.SMTPException:
            logger.exception("support: ticket %s creado, pero falló el envío SMTP.", ticket.id)
        except Exception:
            logger.exception("support: ticket %s creado, error inesperado enviando email.", ticket.id)

        return jsonify(SupportTicketDetailSchema().dump(ticket)), 201


# ─────────────────────────────────────────────────────────────────────────
# Conteo de mensajes admin no leídos por el usuario actual
# ─────────────────────────────────────────────────────────────────────────
@blp.route("/tickets/unread-count")
class TicketUnreadCount(MethodView):

    @jwt_required()
    def get(self):
        user = _current_user()
        if not user:
            return jsonify({"unread_count": 0}), 200
        count = TicketHandler.count_unread_for_user(user.id)
        return jsonify({"unread_count": count}), 200


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

        # Si quien abre es el dueño, marcamos como leídas las respuestas
        # admin que tuviera pendientes.
        if ticket.user_id == user.id:
            TicketHandler.mark_admin_replies_as_read(ticket)

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
