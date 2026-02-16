from extensions import db
from datetime import datetime

class Record(db.Model):
    __tablename__ = "records"

    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(
        db.Integer,
        db.ForeignKey("tables.id", ondelete="CASCADE"),
        nullable=False
    )

    data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    table = db.relationship(
        "Table",
        backref=db.backref(
            "records",
            cascade="all, delete-orphan",
            passive_deletes=True
        )
    )
