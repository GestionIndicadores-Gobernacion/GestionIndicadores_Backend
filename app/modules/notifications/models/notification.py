# app/modules/notifications/models/notification.py
from app.core.extensions import db
from datetime import datetime

# ── Categorías de notificación (evita magic strings dispersos) ───────────
# El frontend enruta por estas mismas cadenas; no cambiar su valor.
CATEGORY_ACTION_PLAN = "action_plan"
CATEGORY_ACTION_PLAN_REMINDER = "action_plan_reminder"
# Un mismo valor sirve para ambos sentidos del chat de soporte: la campana
# enruta admin → /support y usuario → FAB según el rol del destinatario.
CATEGORY_SUPPORT_REPLY = "support_reply"


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, default="action_plan")
    entity_id = db.Column(db.Integer, nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))

    def __repr__(self):
        return f"<Notification {self.id} -> user={self.user_id} read={self.is_read}>"