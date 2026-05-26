# app/modules/support/services/ticket_handler.py
"""
Servicio para crear y manipular tickets de soporte.
"""
from datetime import datetime
from typing import List, Optional, Tuple

from app.core.extensions import db
from app.modules.notifications.services.notification_handler import NotificationHandler
from app.modules.support.models.message import SupportMessage
from app.modules.support.models.ticket import SupportTicket, TICKET_STATUSES
from app.shared.models.user import User


def _build_title(message: str) -> str:
    """Construye un título corto a partir del primer mensaje."""
    snippet = (message or "").strip().split("\n", 1)[0]
    if len(snippet) > 120:
        snippet = snippet[:117] + "…"
    return snippet or "Reporte sin título"


class TicketHandler:

    @staticmethod
    def create(
        *,
        user_id: int,
        message: str,
        current_url: str = "",
        user_agent: str = "",
    ) -> SupportTicket:
        ticket = SupportTicket(
            user_id=user_id,
            title=_build_title(message),
            current_url=(current_url or "")[:1000] or None,
            user_agent=(user_agent or "")[:500] or None,
            status="pendiente",
        )
        db.session.add(ticket)
        db.session.flush()  # Necesitamos el id para el primer mensaje.

        first_msg = SupportMessage(
            ticket_id=ticket.id,
            user_id=user_id,
            body=message,
            is_admin_reply=False,
            read_by_owner=True,  # El propio autor ya lo leyó.
        )
        db.session.add(first_msg)
        db.session.commit()
        return ticket

    @staticmethod
    def list_for_user(user_id: int) -> List[SupportTicket]:
        return (
            SupportTicket.query
            .filter_by(user_id=user_id)
            .order_by(SupportTicket.updated_at.desc())
            .all()
        )

    @staticmethod
    def list_all(status: Optional[str] = None) -> List[SupportTicket]:
        q = SupportTicket.query
        if status and status in TICKET_STATUSES:
            q = q.filter_by(status=status)
        return q.order_by(SupportTicket.updated_at.desc()).all()

    @staticmethod
    def get(ticket_id: int) -> Optional[SupportTicket]:
        return SupportTicket.query.get(ticket_id)

    @staticmethod
    def count_unread_for_user(user_id: int) -> int:
        """Cuántas respuestas de admin sin leer tiene el usuario en total."""
        return (
            db.session.query(SupportMessage)
            .join(SupportTicket, SupportTicket.id == SupportMessage.ticket_id)
            .filter(
                SupportTicket.user_id == user_id,
                SupportMessage.is_admin_reply.is_(True),
                SupportMessage.read_by_owner.is_(False),
            )
            .count()
        )

    @staticmethod
    def mark_admin_replies_as_read(ticket: SupportTicket) -> int:
        """
        Marca como leídas todas las respuestas de admin del ticket. Devuelve
        cuántas se marcaron. Llamar cuando el dueño abre el ticket.
        """
        unread = [m for m in ticket.messages if m.is_admin_reply and not m.read_by_owner]
        for m in unread:
            m.read_by_owner = True
        if unread:
            db.session.commit()
        return len(unread)

    @staticmethod
    def add_message(
        *,
        ticket: SupportTicket,
        author: User,
        body: str,
    ) -> Tuple[SupportMessage, Optional[str]]:
        is_admin = bool(author.role and author.role.name == "admin")

        # Si un admin responde un ticket "pendiente", lo movemos a en_proceso
        # automáticamente para reflejar que ya hay alguien atendiéndolo.
        if is_admin and ticket.status == "pendiente":
            ticket.status = "en_proceso"

        msg = SupportMessage(
            ticket_id=ticket.id,
            user_id=author.id,
            body=body,
            is_admin_reply=is_admin,
            # Si el autor del mensaje es el dueño, lo marcamos como leído
            # (no aplica el flag); si es admin, queda no leído para el dueño.
            read_by_owner=not is_admin,
        )
        db.session.add(msg)
        ticket.updated_at = datetime.utcnow()
        db.session.commit()

        # Notificación in-app cuando admin responde a un ticket de otro
        # usuario. Si admin se contesta a sí mismo, no la creamos.
        if is_admin and ticket.user_id != author.id:
            NotificationHandler.create(
                user_id=ticket.user_id,
                title="Respuesta a tu reporte",
                message=(body[:160] + "…") if len(body) > 160 else body,
                category="support_reply",
                entity_id=ticket.id,
            )
            db.session.commit()

        return msg, None

    @staticmethod
    def update_status(ticket: SupportTicket, new_status: str) -> Tuple[Optional[SupportTicket], Optional[str]]:
        if new_status not in TICKET_STATUSES:
            return None, f"Estado '{new_status}' no es válido."
        if ticket.status == new_status:
            return ticket, None
        ticket.status = new_status
        ticket.updated_at = datetime.utcnow()
        db.session.commit()
        return ticket, None
