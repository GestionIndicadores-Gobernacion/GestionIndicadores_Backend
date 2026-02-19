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

    name = db.Column(db.String(255), nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relaciones
    strategy = db.relationship(
        "Strategy",
        back_populates="components"
    )

    objectives = db.relationship(
        "ComponentObjective",
        back_populates="component",
        cascade="all, delete-orphan"
    )

    mga_activities = db.relationship(
        "ComponentMGAActivity",
        back_populates="component",
        cascade="all, delete-orphan"
    )

    indicators = db.relationship(
        "ComponentIndicator",
        back_populates="component",
        cascade="all, delete-orphan",
        order_by="ComponentIndicator.order"
    )

    reports = db.relationship(
        "Report",
        back_populates="component",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "strategy_id",
            "name",
            name="uq_component_strategy_name"
        ),
    )

    def __repr__(self):
        return f"<Component {self.id} - {self.name}>"