from marshmallow import Schema, fields, validate


class IndicatorTargetSchema(Schema):
    id           = fields.Int(dump_only=True)
    year         = fields.Int(dump_only=True)
    target_value = fields.Float(dump_only=True)


class IndicatorMetaSchema(Schema):
    id          = fields.Int(dump_only=True)
    name        = fields.Str(dump_only=True)
    field_type  = fields.Str(dump_only=True)
    is_required = fields.Bool(dump_only=True)
    config      = fields.Raw(dump_only=True)
    targets     = fields.List(fields.Nested(IndicatorTargetSchema), dump_only=True)


class ReportIndicatorValueSchema(Schema):
    indicator_id = fields.Int(required=True)
    value        = fields.Raw(required=True, allow_none=True)
    indicator    = fields.Nested(IndicatorMetaSchema, dump_only=True)


class ReportSchema(Schema):

    id           = fields.Int(dump_only=True)
    user_id      = fields.Int(dump_only=True, allow_none=True)  # ← NUEVO

    strategy_id  = fields.Int(required=True)
    component_id = fields.Int(required=True)

    report_date  = fields.Date(required=True)

    executive_summary     = fields.Str(required=True)
    intervention_location = fields.Str(required=True)

    zone_type = fields.Str(
        required=True,
        validate=validate.OneOf(["Urbana", "Rural"])
    )

    evidence_link = fields.Str(allow_none=True)
    action_plan_activity_id     = fields.Int(load_default=None, allow_none=True)
    
    indicator_values = fields.List(
        fields.Nested(ReportIndicatorValueSchema),
        required=True
    )

    created_at = fields.DateTime(dump_only=True)
    