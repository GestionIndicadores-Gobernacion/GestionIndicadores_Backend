from extensions import db
from datetime import datetime

class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)

    strategy_id = db.Column(
        db.Integer,
        db.ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False
    )

    description = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, default=True)

    components = db.relationship(
        "Component",
        backref="activity",
        cascade="all, delete",
        passive_deletes=True
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
