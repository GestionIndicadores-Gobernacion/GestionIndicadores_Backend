from extensions import db


class StrategyMetric(db.Model):
    __tablename__ = "strategy_metrics"

    id = db.Column(db.Integer, primary_key=True)

    strategy_id = db.Column(
        db.Integer,
        db.ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False
    )

    description = db.Column(db.Text, nullable=False)
    
    manual_value = db.Column(db.Numeric(14, 2), nullable=True)

    metric_type = db.Column(
        db.String(50),
        nullable=False
    )

    component_id = db.Column(
        db.Integer,
        db.ForeignKey("components.id"),
        nullable=True
    )

    field_name = db.Column(
        db.String(100),
        nullable=True
    )

    # ID del dataset externo (usado en dataset_count y dataset_sum)
    dataset_id = db.Column(
        db.Integer,
        db.ForeignKey("datasets.id"),
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

    dataset = db.relationship(
        "Dataset",
        lazy=True
    )

    def __repr__(self):
        return f"<StrategyMetric {self.id} Strategy:{self.strategy_id}>"