from app.modules.indicators.models.Strategy.strategy_metric import StrategyMetric
from app.modules.indicators.models.Strategy.strategy import Strategy
from app.modules.indicators.constants.metric_types import METRIC_TYPES


class StrategyMetricValidator:

    @staticmethod
    def validate_create(data):

        errors = {}

        if "strategy_id" not in data:
            errors["strategy_id"] = "Strategy is required"
        else:
            strategy = Strategy.query.get(data["strategy_id"])
            if not strategy:
                errors["strategy_id"] = "Strategy not found"

        if not data.get("description"):
            errors["description"] = "Description is required"

        if data.get("metric_type") not in METRIC_TYPES:  # ← centralizado
            errors["metric_type"] = f"Invalid metric_type. Allowed: {METRIC_TYPES}"

        return errors