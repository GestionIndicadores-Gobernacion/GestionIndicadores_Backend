from marshmallow import Schema, fields, validate


class ActionPlanSupportStaffSchema(Schema):
    id   = fields.Int(dump_only=True)
    name = fields.Str(required=True)


class ActionPlanActivitySchema(Schema):
    id                       = fields.Int(dump_only=True)
    plan_objective_id        = fields.Int(dump_only=True)
    name                     = fields.Str(required=True)
    deliverable              = fields.Str(required=True)
    delivery_date            = fields.Date(format="iso", required=True)
    requires_boss_assistance = fields.Bool(load_default=False)
    evidence_url             = fields.Str(dump_only=True, allow_none=True)
    description              = fields.Str(dump_only=True, allow_none=True)
    reported_at              = fields.DateTime(dump_only=True, allow_none=True)
    score                    = fields.Int(dump_only=True, allow_none=True)
    status                   = fields.Str(dump_only=True)
    support_staff            = fields.List(fields.Nested(ActionPlanSupportStaffSchema), load_default=[])


class ActionPlanObjectiveSchema(Schema):
    id             = fields.Int(dump_only=True)
    objective_id   = fields.Int(load_default=None, allow_none=True)
    objective_text = fields.Str(load_default=None, allow_none=True)
    activities     = fields.List(
        fields.Nested(ActionPlanActivitySchema),
        required=True,
        validate=validate.Length(min=1)
    )


class ActionPlanCreateSchema(Schema):
    strategy_id     = fields.Int(required=True)
    component_id    = fields.Int(required=True)
    responsible     = fields.Str(load_default=None, allow_none=True)
    plan_objectives = fields.List(
        fields.Nested(ActionPlanObjectiveSchema),
        required=True,
        validate=validate.Length(min=1)
    )


class ActionPlanActivityReportSchema(Schema):
    evidence_url = fields.Str(required=True)
    description  = fields.Str(load_default=None, allow_none=True)


class ActionPlanResponseSchema(Schema):
    id              = fields.Int(dump_only=True)
    user_id         = fields.Int(dump_only=True, allow_none=True)  # ← NUEVO
    strategy_id     = fields.Int()
    component_id    = fields.Int()
    responsible     = fields.Str(allow_none=True)
    total_score     = fields.Int(dump_only=True)                   # ← NUEVO
    plan_objectives = fields.List(fields.Nested(ActionPlanObjectiveSchema), dump_only=True)
    created_at      = fields.DateTime(dump_only=True)
    updated_at      = fields.DateTime(dump_only=True)


# Nota: este schema está duplicado en tu archivo original,
# la segunda definición sobreescribe la primera.
# Aquí se unifica en una sola versión completa:
class ActionPlanActivityDetailSchema(Schema):
    id            = fields.Int(dump_only=True)
    evidence_url  = fields.Str(dump_only=True, allow_none=True)
    description   = fields.Str(dump_only=True, allow_none=True)
    reported_at   = fields.DateTime(dump_only=True, allow_none=True)
    score         = fields.Int(dump_only=True, allow_none=True)
    status        = fields.Str(dump_only=True)
    support_staff = fields.List(fields.Nested(ActionPlanSupportStaffSchema), dump_only=True)