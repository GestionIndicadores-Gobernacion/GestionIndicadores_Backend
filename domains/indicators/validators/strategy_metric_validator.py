from domains.indicators.models.Strategy.strategy_metric import StrategyMetric
from domains.indicators.models.Strategy.strategy import Strategy


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

        metric_type = data.get("metric_type")

        allowed = [
            "dataset_sum",
            "report_count",
            "report_sum",
            "manual"
        ]

        if metric_type not in allowed:
            errors["metric_type"] = "Invalid metric_type"

        return errors