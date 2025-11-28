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

    # Si en algún momento quieres texto/numérico/etc., lo dejamos
    data_type = db.Column(db.String(50), nullable=False, default="integer")

    active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    component = db.relationship("Component", backref="indicators")

    def __repr__(self):
        return f"<Indicator {self.name}>"
