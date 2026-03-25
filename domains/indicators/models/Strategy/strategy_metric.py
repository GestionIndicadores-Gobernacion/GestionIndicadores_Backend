from extensions import db


class StrategyMetric(db.Model):
    __tablename__ = "strategy_metrics"

    id = db.Column(db.Integer, primary_key=True)

    strategy_id = db.Column(
        db.Integer,
        db.ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False
    )

    # descripción de cómo se mide la meta
    description = db.Column(db.Text, nullable=False)

    # tipo de métrica
    metric_type = db.Column(
        db.String(50),
        nullable=False
    )
    """
    Valores esperados:
    - dataset_sum
    - report_count
    - report_sum
    - manual
    """

    # componente relacionado (opcional)
    component_id = db.Column(
        db.Integer,
        db.ForeignKey("components.id"),
        nullable=True
    )

    # campo del reporte que se debe sumar
    field_name = db.Column(
        db.String(100),
        nullable=True
    )

    strategy = db.relationship(
        "Strategy",
        back_populates="metrics"
    )

    component = db.relationship(
        "Component",
        lazy=True
    )

    def __repr__(self):
        return f"<StrategyMetric {self.id} Strategy:{self.strategy_id}>"