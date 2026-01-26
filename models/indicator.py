from extensions import db
from datetime import datetime

class Indicator(db.Model):
    __tablename__ = "indicators"

    id = db.Column(db.Integer, primary_key=True)

    component_id = db.Column(
        db.Integer,
        db.ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False
    )

    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(500), nullable=True)

    data_type = db.Column(db.String(50), nullable=False, default="integer")
    meta = db.Column(db.Float, nullable=False)

    es_poblacional = db.Column(db.Boolean, default=False, nullable=False)  # 🔥 NUEVO

    active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<Indicator {self.name} - Meta {self.meta}>"
