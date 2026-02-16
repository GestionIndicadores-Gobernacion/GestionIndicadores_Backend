from extensions import db
from datetime import datetime


class ComponentIndicatorTarget(db.Model):
    __tablename__ = "component_indicator_targets"

    id = db.Column(db.Integer, primary_key=True)

    indicator_id = db.Column(
        db.Integer,
        db.ForeignKey("component_indicators.id", ondelete="CASCADE"),
        nullable=False
    )

    year = db.Column(db.Integer, nullable=False)

    target_value = db.Column(
        db.Float,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            "indicator_id",
            "year",
            name="uq_indicator_year"
        ),
    )

    def __repr__(self):
        return f"<IndicatorTarget {self.indicator_id} - {self.year}>"
