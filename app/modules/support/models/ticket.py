# app/modules/support/models/ticket.py
from datetime import datetime

from app.core.extensions import db

# Estados válidos del flujo. El backend valida que los cambios solo usen
# valores de esta lista; cualquier valor fuera de aquí debe rechazarse en
# las rutas/handlers.
TICKET_STATUSES = ("pendiente", "en_proceso", "resuelto", "cerrado")


class SupportTicket(db.Model):
    __tablename__ = "support_tickets"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Resumen visible en la lista (primeras palabras del primer mensaje).
    title = db.Column(db.String(160), nullable=False)

    # Contexto técnico capturado al crear el ticket.
    current_url = db.Column(db.String(1000), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)

    status = db.Column(
        db.String(20),
        nullable=False,
        default="pendiente",
        index=True,
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = db.relationship("User", backref=db.backref("support_tickets", lazy="dynamic"))
    messages = db.relationship(
        "SupportMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="SupportMessage.created_at.asc()",
        lazy="select",
    )

    def __repr__(self):
        return f"<SupportTicket {self.id} user={self.user_id} status={self.status}>"
