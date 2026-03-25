from marshmallow import Schema, fields, validate


class StrategyMetricSchema(Schema):

    class Meta:
        title = "Strategy Metric Schema"

    id = fields.Int(dump_only=True)

    strategy_id = fields.Int(required=True)

    description = fields.Str(required=True)

    metric_type = fields.Str(
        required=True,
        validate=validate.OneOf([
            "dataset_sum",
            "report_count",
            "report_sum",
            "manual"
        ])
    )

    component_id = fields.Int(allow_none=True)

    field_name = fields.Str(allow_none=True)