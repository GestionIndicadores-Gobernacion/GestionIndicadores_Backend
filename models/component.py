from extensions import db
from datetime import datetime

class Component(db.Model):
    __tablename__ = "components"

    id = db.Column(db.Integer, primary_key=True)

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False
    )

    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(500))
    data_type = db.Column(db.String(50), nullable=False, default="integer")
    active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    indicators = db.relationship(
        "Indicator",
        backref="component",
        cascade="all, delete",
        passive_deletes=True
    )
