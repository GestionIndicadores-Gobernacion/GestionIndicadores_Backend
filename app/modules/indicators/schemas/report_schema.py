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


# ── Schemas anidados para relaciones ─────────────────────────────────────────

class ComponentSummarySchema(Schema):
    id   = fields.Int(dump_only=True)
    name = fields.Str(dump_only=True)


class StrategySummarySchema(Schema):
    id   = fields.Int(dump_only=True)
    name = fields.Str(dump_only=True)


class UserSummarySchema(Schema):
    id   = fields.Int(dump_only=True)
    name = fields.Str(dump_only=True)


class ReportSchema(Schema):

    id           = fields.Int(dump_only=True)
    user_id      = fields.Int(dump_only=True, allow_none=True)

    strategy_id  = fields.Int(required=True)
    component_id = fields.Int(required=True)

    report_date  = fields.Date(required=True)

    executive_summary     = fields.Str(required=True)
    intervention_location = fields.Str(required=True)

    zone_type = fields.Str(
        required=True,
        validate=validate.OneOf(["Urbana", "Rural"])
    )

    evidence_link           = fields.Str(allow_none=True)
    action_plan_activity_id = fields.Int(load_default=None, allow_none=True)

    indicator_values = fields.List(
        fields.Nested(ReportIndicatorValueSchema),
        required=True
    )

    created_at = fields.DateTime(dump_only=True)

    # ── Relaciones enriquecidas (solo dump) ───────────────────────
    component = fields.Nested(ComponentSummarySchema, dump_only=True)
    strategy  = fields.Nested(StrategySummarySchema,  dump_only=True)
    user      = fields.Nested(UserSummarySchema,       dump_only=True)


# ─────────────────────────────────────────────────────────────────────
# SCHEMAS ALIGERADOS PARA LISTADOS (/reports/all)
#
# El frontend en lista (tabla + dashboard map) NO usa:
#   - indicator.targets   (lazy → N+1 al dumpar)
#   - indicator.config    (JSON pesado por indicador)
#   - indicator.is_required
#   - relaciones nested `component` / `strategy` / `user`
#     (se resuelven por id vía strategyMap/componentMap en el cliente)
#
# Pero SÍ usa `indicator_values[*].indicator.{id,name,field_type}`
# (el mapa del dashboard agrupa por nombre/tipo). Por eso se mantiene
# `indicator` en versión lite.
#
# El schema completo (`ReportSchema`) sigue intacto y se sigue usando
# en endpoints de detalle / create / update.
# ─────────────────────────────────────────────────────────────────────


class IndicatorLiteSchema(Schema):
    id         = fields.Int(dump_only=True)
    name       = fields.Str(dump_only=True)
    field_type = fields.Str(dump_only=True)


class ReportIndicatorValueLiteSchema(Schema):
    indicator_id = fields.Int(dump_only=True)
    value        = fields.Raw(dump_only=True, allow_none=True)
    indicator    = fields.Nested(IndicatorLiteSchema, dump_only=True)


class ReportListSchema(Schema):
    """Forma reducida de `Report` para listas / dashboards."""

    id                      = fields.Int(dump_only=True)
    user_id                 = fields.Int(dump_only=True, allow_none=True)

    strategy_id             = fields.Int(dump_only=True)
    component_id            = fields.Int(dump_only=True)

    report_date             = fields.Date(dump_only=True)
    executive_summary       = fields.Str(dump_only=True)
    intervention_location   = fields.Str(dump_only=True)
    zone_type               = fields.Str(dump_only=True)
    evidence_link           = fields.Str(dump_only=True, allow_none=True)
    action_plan_activity_id = fields.Int(dump_only=True, allow_none=True)

    created_at              = fields.DateTime(dump_only=True)

    indicator_values = fields.List(
        fields.Nested(ReportIndicatorValueLiteSchema),
        dump_only=True,
    )