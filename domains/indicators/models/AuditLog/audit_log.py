from extensions import db
from datetime import datetime, timezone


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    entity    = db.Column(db.String(50),  nullable=False)  # "report" | "action_plan"
    entity_id = db.Column(db.Integer,     nullable=False)
    action    = db.Column(db.String(20),  nullable=False)  # "created" | "updated" | "deleted"
    detail    = db.Column(db.Text,        nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    user = db.relationship("User", backref=db.backref("audit_logs", lazy=True))

    def __repr__(self):
        return f"<AuditLog {self.action} {self.entity}#{self.entity_id} by user#{self.user_id}>"