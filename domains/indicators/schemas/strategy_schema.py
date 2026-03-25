# domains/indicators/schemas/strategy_schema.py
from marshmallow import Schema, fields, validate, EXCLUDE

from domains.indicators.constants.metric_types import METRIC_TYPES


class StrategyAnnualGoalSchema(Schema):

    class Meta:
        unknown = EXCLUDE

    year_number = fields.Int(required=True, validate=validate.Range(min=1))
    value       = fields.Decimal(required=True, as_string=True)


class StrategyMetricSchema(Schema):

    class Meta:
        unknown = EXCLUDE

    id           = fields.Int(dump_only=True)
    description  = fields.Str(required=True)
    metric_type  = fields.Str(required=True, validate=validate.OneOf(METRIC_TYPES))
    component_id = fields.Int(allow_none=True)
    field_name   = fields.Str(allow_none=True)


class StrategySchema(Schema):

    class Meta:
        unknown = EXCLUDE

    id                       = fields.Int(dump_only=True)
    name                     = fields.Str(required=True)
    objective                = fields.Str(required=True)
    product_goal_description = fields.Str(required=True)

    annual_goals = fields.List(fields.Nested(StrategyAnnualGoalSchema), load_default=[])
    metrics      = fields.List(fields.Nested(StrategyMetricSchema),      load_default=[])

    # total_goal es un @property en el modelo — fields.Decimal no lo detecta
    total_goal = fields.Method("get_total_goal", dump_only=True)

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    def get_total_goal(self, obj):
        val = getattr(obj, 'total_goal', None)
        return str(val) if val is not None else "0"