from extensions import db
from datetime import datetime

class Dataset(db.Model):
    __tablename__ = "datasets"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tables = db.relationship(
        "Table",
        back_populates="dataset",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
