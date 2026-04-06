from marshmallow import Schema, fields, validate


class ActionPlanSupportStaffSchema(Schema):
    id   = fields.Int(dump_only=True)
    name = fields.Str(required=True)


class RecurrenceSchema(Schema):
    """Regla de recurrencia para una actividad."""
    frequency    = fields.Str(
        required=True,
        validate=validate.OneOf(["daily", "weekly", "biweekly", "monthly", "yearly", "custom"])
    )
    until        = fields.Date(format="iso", required=True)   # fecha límite
    day_of_month = fields.Int(load_default=None, allow_none=True)  # para monthly
    day_of_week  = fields.Int(load_default=None, allow_none=True)  # 0=lun..6=dom
    interval     = fields.Int(load_default=7, allow_none=True)     # para custom


class ActionPlanActivitySchema(Schema):
    id                       = fields.Int(dump_only=True)
    plan_objective_id        = fields.Int(dump_only=True)
    name                     = fields.Str(required=True)
    deliverable              = fields.Str(required=True)
    delivery_date            = fields.Date(format="iso", required=True)
    lugar                    = fields.Str(required=True)
    requires_boss_assistance = fields.Bool(load_default=False)
    evidence_url             = fields.Str(dump_only=True, allow_none=True)
    description              = fields.Str(dump_only=True, allow_none=True)
    reported_at              = fields.DateTime(dump_only=True, allow_none=True)
    score                    = fields.Int(dump_only=True, allow_none=True)
    status                   = fields.Str(dump_only=True)
    support_staff            = fields.List(fields.Nested(ActionPlanSupportStaffSchema), load_default=[])

    # Recurrencia — solo al crear/editar, no se serializa en respuesta
    recurrence               = fields.Nested(RecurrenceSchema, load_default=None, allow_none=True, load_only=True)

    # Campos de recurrencia en respuesta
    recurrence_group_id      = fields.Str(dump_only=True, allow_none=True)
    recurrence_rule          = fields.Dict(dump_only=True, allow_none=True)


class ActionPlanActivityEditSchema(Schema):
    """Schema para editar una actividad existente."""
    name                     = fields.Str(required=True)
    deliverable              = fields.Str(required=True)
    delivery_date            = fields.Date(format="iso", load_default=None, allow_none=True)
    lugar                    = fields.Str(required=True)
    requires_boss_assistance = fields.Bool(load_default=False)
    support_staff            = fields.List(fields.Nested(ActionPlanSupportStaffSchema), load_default=[])
    edit_all                 = fields.Bool(load_default=False)  # True = editar todo el grupo


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
    user_id         = fields.Int(dump_only=True, allow_none=True)
    strategy_id     = fields.Int()
    component_id    = fields.Int()
    responsible     = fields.Str(allow_none=True)
    total_score     = fields.Int(dump_only=True)
    plan_objectives = fields.List(fields.Nested(ActionPlanObjectiveSchema), dump_only=True)
    created_at      = fields.DateTime(dump_only=True)
    updated_at      = fields.DateTime(dump_only=True)


class ActionPlanActivityDetailSchema(Schema):
    id                  = fields.Int(dump_only=True)
    evidence_url        = fields.Str(dump_only=True, allow_none=True)
    description         = fields.Str(dump_only=True, allow_none=True)
    reported_at         = fields.DateTime(dump_only=True, allow_none=True)
    score               = fields.Int(dump_only=True, allow_none=True)
    status              = fields.Str(dump_only=True)
    recurrence_group_id = fields.Str(dump_only=True, allow_none=True)
    recurrence_rule     = fields.Dict(dump_only=True, allow_none=True)
    support_staff       = fields.List(fields.Nested(ActionPlanSupportStaffSchema), dump_only=True)