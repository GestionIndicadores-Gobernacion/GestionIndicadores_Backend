# app/modules/support/services/ticket_handler.py
"""
Servicio para crear y manipular tickets de soporte.
"""
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import func

from app.core.extensions import db
from app.modules.notifications.models.notification import CATEGORY_SUPPORT_REPLY
from app.modules.notifications.services.notification_handler import NotificationHandler
from app.modules.support.models.message import SupportMessage
from app.modules.support.models.ticket import SupportTicket, TICKET_STATUSES
from app.shared.models.role import Role
from app.shared.models.user import User


def _build_title(message: str) -> str:
    """Construye un título corto a partir del primer mensaje."""
    snippet = (message or "").strip().split("\n", 1)[0]
    if len(snippet) > 120:
        snippet = snippet[:117] + "…"
    return snippet or "Reporte sin título"


def _preview(body: str, images) -> str:
    """Texto corto para la notificación a partir del cuerpo o las imágenes."""
    text = (body or "").strip()
    if not text and images:
        n = len(images)
        return "📷 Imagen adjunta" if n == 1 else f"📷 {n} imágenes adjuntas"
    return text[:160] + "…" if len(text) > 160 else text


def _active_admin_ids(exclude_id: int | None = None) -> list[int]:
    """IDs de todos los admins activos (para avisar de tickets nuevos)."""
    rows = (
        db.session.query(User.id)
        .join(Role, Role.id == User.role_id)
        .filter(Role.name == "admin", User.is_active.is_(True))
        .all()
    )
    return [uid for (uid,) in rows if uid != exclude_id]


def _ticket_admin_participant_ids(ticket: SupportTicket, exclude_id: int | None = None) -> list[int]:
    """Admins que ya han escrito en el ticket (los que lo están atendiendo)."""
    ids = {
        m.user_id for m in ticket.messages
        if m.is_admin_reply and m.user_id and m.user_id != exclude_id
    }
    return list(ids)


class TicketHandler:

    @staticmethod
    def create(
        *,
        user_id: int,
        message: str,
        current_url: str = "",
        user_agent: str = "",
        images: Optional[List[str]] = None,
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
            read_by_owner=True,   # El propio autor ya lo leyó.
            read_by_admin=False,  # Ningún admin lo ha visto todavía.
            images=list(images) if images else None,
        )
        db.session.add(first_msg)
        db.session.flush()

        # Aviso in-app a todos los admins de que entró un reporte nuevo.
        preview = _preview(message, images)
        for admin_id in _active_admin_ids(exclude_id=user_id):
            NotificationHandler.create(
                user_id=admin_id,
                title="Nuevo reporte de soporte",
                message=preview,
                category=CATEGORY_SUPPORT_REPLY,
                entity_id=ticket.id,
            )

        db.session.commit()
        return ticket

    @staticmethod
    def list_for_user(user_id: int) -> List[SupportTicket]:
        tickets = (
            SupportTicket.query
            .filter_by(user_id=user_id)
            .order_by(SupportTicket.updated_at.desc())
            .all()
        )
        TicketHandler._attach_summaries(tickets)
        return tickets

    @staticmethod
    def list_all(status: Optional[str] = None) -> List[SupportTicket]:
        q = SupportTicket.query
        if status and status in TICKET_STATUSES:
            q = q.filter_by(status=status)
        tickets = q.order_by(SupportTicket.updated_at.desc()).all()
        TicketHandler._attach_summaries(tickets)
        return tickets

    @staticmethod
    def _attach_summaries(tickets: List[SupportTicket]) -> None:
        """Precalcula preview del último mensaje y conteos de no leídos en unas
        pocas consultas agregadas y los adjunta como atributos transitorios,
        para que el schema NO recorra `ticket.messages` por cada ticket (N+1)."""
        ids = [t.id for t in tickets]
        if not ids:
            return

        # Conteo de respuestas admin sin leer por el dueño (badge del usuario).
        owner_unread = dict(
            db.session.query(SupportMessage.ticket_id, func.count(SupportMessage.id))
            .filter(
                SupportMessage.ticket_id.in_(ids),
                SupportMessage.is_admin_reply.is_(True),
                SupportMessage.read_by_owner.is_(False),
            )
            .group_by(SupportMessage.ticket_id)
            .all()
        )
        # Conteo de mensajes de usuario sin leer por el admin (badge admin).
        admin_unread = dict(
            db.session.query(SupportMessage.ticket_id, func.count(SupportMessage.id))
            .filter(
                SupportMessage.ticket_id.in_(ids),
                SupportMessage.is_admin_reply.is_(False),
                SupportMessage.read_by_admin.is_(False),
            )
            .group_by(SupportMessage.ticket_id)
            .all()
        )
        # Último mensaje de cada ticket (una fila por ticket, no todos).
        last_ids_sq = (
            db.session.query(func.max(SupportMessage.id))
            .filter(SupportMessage.ticket_id.in_(ids))
            .group_by(SupportMessage.ticket_id)
        )
        last_msgs = (
            SupportMessage.query
            .filter(SupportMessage.id.in_(last_ids_sq))
            .all()
        )
        preview_by_ticket = {
            m.ticket_id: _preview(m.body, m.image_list) for m in last_msgs
        }

        for t in tickets:
            t._summary_last_preview = preview_by_ticket.get(t.id)
            t._summary_unread_owner = owner_unread.get(t.id, 0)
            t._summary_unread_admin = admin_unread.get(t.id, 0)

    @staticmethod
    def get(ticket_id: int) -> Optional[SupportTicket]:
        return SupportTicket.query.get(ticket_id)

    @staticmethod
    def messages_after(ticket_id: int, after_id: int = 0) -> List[SupportMessage]:
        """Mensajes del ticket con id > after_id, en orden cronológico. Permite
        al frontend hacer polling incremental sin re-descargar todo el hilo."""
        return (
            SupportMessage.query
            .filter(
                SupportMessage.ticket_id == ticket_id,
                SupportMessage.id > (after_id or 0),
            )
            .order_by(SupportMessage.id.asc())
            .all()
        )

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
    def count_unread_for_admin() -> int:
        """Cuántos tickets tienen mensajes de usuario sin leer por ningún admin
        (excluye tickets cerrados). Es el badge del panel de administración."""
        rows = (
            db.session.query(SupportMessage.ticket_id)
            .join(SupportTicket, SupportTicket.id == SupportMessage.ticket_id)
            .filter(
                SupportMessage.is_admin_reply.is_(False),
                SupportMessage.read_by_admin.is_(False),
                SupportTicket.status != "cerrado",
            )
            .distinct()
            .count()
        )
        return rows

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
    def mark_user_messages_as_read_by_admin(ticket: SupportTicket) -> int:
        """Marca como vistos por el admin los mensajes escritos por el usuario.
        Llamar cuando un admin abre el ticket. Simétrico al del dueño."""
        unread = [m for m in ticket.messages if not m.is_admin_reply and not m.read_by_admin]
        for m in unread:
            m.read_by_admin = True
        if unread:
            db.session.commit()
        return len(unread)

    @staticmethod
    def add_message(
        *,
        ticket: SupportTicket,
        author: User,
        body: str,
        images: Optional[List[str]] = None,
    ) -> Tuple[SupportMessage, Optional[str]]:
        is_admin = bool(author.role and author.role.name == "admin")

        # Transiciones automáticas de estado según quién escribe:
        # - admin responde ticket "pendiente" → "en_proceso" (alguien lo atiende).
        # - usuario responde ticket "resuelto" → "en_proceso" (lo reabre): así
        #   la respuesta no queda invisible bajo un estado cerrado-lógico.
        if is_admin and ticket.status == "pendiente":
            ticket.status = "en_proceso"
        elif not is_admin and ticket.status == "resuelto":
            ticket.status = "en_proceso"

        msg = SupportMessage(
            ticket_id=ticket.id,
            user_id=author.id,
            body=body or "",
            is_admin_reply=is_admin,
            # Cada mensaje nace leído por su propio lado y sin leer por el otro:
            # - admin escribe  → leído por admin, sin leer por el dueño.
            # - usuario escribe → leído por el dueño, sin leer por el admin.
            read_by_owner=not is_admin,
            read_by_admin=is_admin,
            images=list(images) if images else None,
        )
        db.session.add(msg)
        ticket.updated_at = datetime.utcnow()

        # ── Notificaciones in-app en AMBOS sentidos ─────────────────────────
        preview = _preview(body, images)
        if is_admin and ticket.user_id != author.id:
            # Admin → dueño del ticket.
            NotificationHandler.create(
                user_id=ticket.user_id,
                title="Respuesta a tu reporte",
                message=preview,
                category=CATEGORY_SUPPORT_REPLY,
                entity_id=ticket.id,
            )
        elif not is_admin:
            # Usuario → admins que ya atienden el ticket; si aún no ha
            # respondido ningún admin, se avisa a todos los admins.
            recipients = _ticket_admin_participant_ids(ticket, exclude_id=author.id)
            if not recipients:
                recipients = _active_admin_ids(exclude_id=author.id)
            title = f"Respuesta en reporte #{ticket.id}"
            for admin_id in recipients:
                NotificationHandler.create(
                    user_id=admin_id,
                    title=title,
                    message=preview,
                    category=CATEGORY_SUPPORT_REPLY,
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
