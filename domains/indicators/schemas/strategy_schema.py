from marshmallow import Schema, fields, validate


class StrategyAnnualGoalSchema(Schema):
    year_number = fields.Int(required=True, validate=validate.Range(min=1))
    value = fields.Decimal(required=True, as_string=True)


class StrategyMetricSchema(Schema):

    id = fields.Int(dump_only=True)

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


class StrategySchema(Schema):

    class Meta:
        title = "Strategy Schema"

    id = fields.Int(dump_only=True)

    name = fields.Str(required=True)
    objective = fields.Str(required=True)
    product_goal_description = fields.Str(required=True)

    # metas por año
    annual_goals = fields.List(
        fields.Nested(StrategyAnnualGoalSchema),
        required=True
    )

    # 👇 MÉTRICAS (nuevo)
    metrics = fields.List(
        fields.Nested(StrategyMetricSchema),
        required=False
    )

    # total calculado
    total_goal = fields.Decimal(dump_only=True, as_string=True)

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)