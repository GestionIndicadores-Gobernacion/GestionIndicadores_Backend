from extensions import db
from datetime import datetime

class Table(db.Model):
    __tablename__ = "tables"

    id = db.Column(db.Integer, primary_key=True)
    dataset_id = db.Column(
        db.Integer,
        db.ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False
    )

    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    dataset = db.relationship(
        "Dataset",
        back_populates="tables"
    )
