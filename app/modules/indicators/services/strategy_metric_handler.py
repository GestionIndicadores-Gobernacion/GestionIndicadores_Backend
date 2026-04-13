from app.core.extensions import db

from app.modules.indicators.models.Strategy.strategy_metric import StrategyMetric
from app.modules.indicators.validators.strategy_metric_validator import StrategyMetricValidator


class StrategyMetricHandler:

    @staticmethod
    def create(data):
        errors = StrategyMetricValidator.validate_create(data)
        if errors:
            return None, errors

        try:
            metric = StrategyMetric(
                strategy_id  = data["strategy_id"],
                description  = data["description"],
                metric_type  = data["metric_type"],
                component_id = data.get("component_id"),
                field_name   = data.get("field_name"),
                dataset_id   = data.get("dataset_id"),
                manual_value = data.get("manual_value"),
                year         = data.get("year"),   # ← nuevo
            )
            db.session.add(metric)
            db.session.commit()
            return metric, None
        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def get_all():
        return StrategyMetric.query.all()

    @staticmethod
    def get_by_id(metric_id):
        return StrategyMetric.query.get(metric_id)

    @staticmethod
    def get_by_strategy(strategy_id):
        return StrategyMetric.query.filter_by(strategy_id=strategy_id).all()

    @staticmethod
    def update(metric, data):
        for field in [
            "description", "metric_type", "component_id",
            "field_name", "dataset_id", "manual_value",
            "year",   # ← nuevo
        ]:
            if field in data:
                setattr(metric, field, data[field])

        db.session.commit()
        return metric

    @staticmethod
    def delete(metric):
        db.session.delete(metric)
        db.session.commit()