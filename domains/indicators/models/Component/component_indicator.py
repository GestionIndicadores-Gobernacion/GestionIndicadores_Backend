from extensions import db
from datetime import datetime


class ComponentIndicator(db.Model):
    __tablename__ = "component_indicators"

    id = db.Column(db.Integer, primary_key=True)

    component_id = db.Column(
        db.Integer,
        db.ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False
    )

    name = db.Column(db.String(255), nullable=False)
    field_type = db.Column(db.String(50), nullable=False)
    config = db.Column(db.JSON, nullable=True)

    is_required = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    component = db.relationship(
        "Component",
        back_populates="indicators"
    )

    targets = db.relationship(
        "ComponentIndicatorTarget",
        backref="indicator",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "component_id",
            "name",
            name="uq_indicator_component_name"
        ),
    )
