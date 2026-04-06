# domains/indicators/schemas/strategy_schema.py
from marshmallow import Schema, fields, validate, EXCLUDE

from domains.indicators.constants.metric_types import METRIC_TYPES


class StrategyAnnualGoalSchema(Schema):

    class Meta:
        unknown = EXCLUDE

    year_number   = fields.Int(required=True, validate=validate.Range(min=1))
    value         = fields.Decimal(required=True, as_string=True)
    calendar_year = fields.Int(dump_only=True)


class StrategyMetricSchema(Schema):

    class Meta:
        unknown = EXCLUDE

    id           = fields.Int(dump_only=True)
    description  = fields.Str(required=True)
    metric_type  = fields.Str(required=True, validate=validate.OneOf(METRIC_TYPES))
    component_id = fields.Int(allow_none=True)
    field_name   = fields.Str(allow_none=True)
    dataset_id   = fields.Int(allow_none=True)
    manual_value = fields.Float(allow_none=True)
    year         = fields.Int(allow_none=True)


class StrategySchema(Schema):

    class Meta:
        unknown = EXCLUDE

    id                       = fields.Int(dump_only=True)
    name                     = fields.Str(required=True)
    objective                = fields.Str(required=True)
    product_goal_description = fields.Str(required=True)

    annual_goals = fields.Method("get_annual_goals", load_default=[])
    metrics      = fields.List(fields.Nested(StrategyMetricSchema), load_default=[])

    total_goal = fields.Method("get_total_goal", dump_only=True)

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    def get_annual_goals(self, obj):
        if obj is None:
            return []

        BASE_YEAR = 2024  # año de inicio fijo del plan de gobierno

        result = []
        for g in obj.annual_goals:
            result.append({
                "year_number":   g.year_number,
                "value":         str(g.value),
                "calendar_year": BASE_YEAR + g.year_number - 1,
            })
        return result

    def get_total_goal(self, obj):
        if obj is None:          # ← mismo guard por seguridad
            return "0"
        try:
            val = sum(float(g.value or 0) for g in obj.annual_goals)
            return str(val)
        except Exception:
            return "0"