from extensions import db
from datetime import datetime


class PublicPolicy(db.Model):
    __tablename__ = "public_policies"

    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(db.String(20), nullable=False, unique=True)  # ej. "1.2", "3.8"
    description = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relación inversa hacia componentes (many-to-many via tabla join)
    components = db.relationship(
        "Component",
        secondary="component_public_policies",
        back_populates="public_policies"
    )

    def __repr__(self):
        return f"<PublicPolicy {self.code}>"