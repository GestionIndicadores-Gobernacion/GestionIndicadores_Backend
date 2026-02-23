from extensions import db


class ReportIndicatorValue(db.Model):
    __tablename__ = "report_indicator_values"

    id = db.Column(db.Integer, primary_key=True)

    report_id = db.Column(
        db.Integer,
        db.ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False
    )

    indicator_id = db.Column(
        db.Integer,
        db.ForeignKey("component_indicators.id", ondelete="CASCADE"),
        nullable=False
    )

    value = db.Column(
        db.JSON,
        nullable=False
    )

    report = db.relationship(
        "Report",
        back_populates="indicator_values"
    )

    # Relación con ComponentIndicator para serializar metadatos en el schema
    indicator = db.relationship(
        "ComponentIndicator",
        lazy="joined"  # joined = un solo query, sin N+1
    )

    __table_args__ = (
        db.UniqueConstraint(
            "report_id",
            "indicator_id",
            name="uq_report_indicator"
        ),
    )