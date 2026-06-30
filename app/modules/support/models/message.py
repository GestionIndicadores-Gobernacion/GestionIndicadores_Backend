# app/modules/support/models/message.py
from datetime import datetime

from app.core.extensions import db


class SupportMessage(db.Model):
    __tablename__ = "support_messages"

    id = db.Column(db.Integer, primary_key=True)

    ticket_id = db.Column(
        db.Integer,
        db.ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Autor del mensaje. Puede ser el dueño del ticket o un admin.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    body = db.Column(db.Text, nullable=False)

    # [LEGADO] Imagen única adjunta como data URL base64. Se mantiene por
    # compatibilidad de lectura con mensajes antiguos; los nuevos usan `images`.
    image_data_url = db.Column(db.Text, nullable=True)

    # Lista de imágenes adjuntas (data URLs base64). Se guardan inline en la BD
    # porque el backend corre en Render con filesystem efímero (no persiste en
    # disco). El frontend las comprime antes de enviarlas para no inflar la fila.
    images = db.Column(db.JSON, nullable=True)

    @property
    def image_list(self) -> list:
        """Lista unificada de imágenes (nuevas + legado de una sola imagen)."""
        if self.images:
            return list(self.images)
        if self.image_data_url:
            return [self.image_data_url]
        return []

    # True cuando lo escribe un usuario con rol admin. Permite distinguir el
    # remitente en la UI sin tener que recargar la relación role en cada
    # render.
    is_admin_reply = db.Column(db.Boolean, default=False, nullable=False)

    # Para que el dueño del ticket pueda ver cuáles respuestas del admin no
    # ha leído todavía. Solo aplica a is_admin_reply=True.
    read_by_owner = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    ticket = db.relationship("SupportTicket", back_populates="messages")
    user = db.relationship("User")

    def __repr__(self):
        return f"<SupportMessage {self.id} ticket={self.ticket_id} admin={self.is_admin_reply}>"
