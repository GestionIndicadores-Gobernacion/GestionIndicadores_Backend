from marshmallow import Schema, fields, validate

from domains.indicators.constants.metric_types import METRIC_TYPES

class StrategyMetricSchema(Schema):

    class Meta:
        title = "Strategy Metric Schema"

    id           = fields.Int(dump_only=True)
    strategy_id  = fields.Int(required=True)
    description  = fields.Str(required=True)
    metric_type  = fields.Str(required=True, validate=validate.OneOf(METRIC_TYPES))
    component_id = fields.Int(allow_none=True)
    field_name   = fields.Str(allow_none=True)
    dataset_id   = fields.Int(allow_none=True)
    manual_value = fields.Float(allow_none=True)
    year         = fields.Int(allow_none=True)   # ← nuevo