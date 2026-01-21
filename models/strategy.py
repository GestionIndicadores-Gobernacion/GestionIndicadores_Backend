from extensions import db
from datetime import datetime

class Strategy(db.Model):
    __tablename__ = "strategies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    description = db.Column(db.String(500), nullable=True)
    active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    activities = db.relationship(
        "Activity",
        backref="strategy",
        cascade="all, delete-orphan",
        passive_deletes=True
    )