from marshmallow import Schema, fields, validate

class StrategyAnnualGoalSchema(Schema):
    year_number = fields.Int(required=True, validate=validate.Range(min=1))
    value = fields.Decimal(required=True, as_string=True)


class StrategySchema(Schema):

    class Meta:
        title = "Strategy Schema"

    id = fields.Int(dump_only=True)

    name = fields.Str(required=True)
    objective = fields.Str(required=True)
    product_goal_description = fields.Str(required=True)

    # 👇 lista de metas por año
    annual_goals = fields.List(
        fields.Nested(StrategyAnnualGoalSchema),
        required=True
    )

    # total calculado (solo salida)
    total_goal = fields.Decimal(dump_only=True, as_string=True)

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
