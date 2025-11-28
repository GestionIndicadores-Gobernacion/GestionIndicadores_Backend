from extensions import db
from datetime import datetime

class Component(db.Model):
    __tablename__ = "components"

    id = db.Column(db.Integer, primary_key=True)

    strategy_id = db.Column(
        db.Integer,
        db.ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False
    )

    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(500), nullable=True)

    data_type = db.Column(db.String(50), nullable=False)

    active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # relación
    strategy = db.relationship("Strategy", backref="components")

    def __repr__(self):
        return f"<Component {self.name}>"
