from marshmallow import Schema, fields
from app.modules.indicators.schemas.component_objective_schema import ComponentObjectiveSchema
from app.modules.indicators.schemas.component_mga_activity_schema import ComponentMGAActivitySchema
from app.modules.indicators.schemas.component_indicator_schema import ComponentIndicatorSchema
from app.modules.indicators.schemas.public_policy_schema import PublicPolicySchema

class ComponentSchema(Schema):

    id          = fields.Int(dump_only=True)
    strategy_id = fields.Int(required=True)
    name        = fields.Str(required=True)

    objectives = fields.List(
        fields.Nested(ComponentObjectiveSchema),
        required=True
    )

    mga_activities = fields.List(
        fields.Nested(ComponentMGAActivitySchema),
        required=True
    )

    indicators = fields.List(
        fields.Nested(ComponentIndicatorSchema),
        required=True
    )

    # ── NUEVO ─────────────────────────────────────────────────────────────
    # Al crear/actualizar: se envían los IDs de las políticas seleccionadas
    public_policy_ids = fields.List(
        fields.Int(),
        load_default=[],          # opcional; por defecto lista vacía
        load_only=True            # solo se usa en input, no se serializa
    )

    # Al leer: se devuelven los objetos completos de políticas públicas
    public_policies = fields.List(
        fields.Nested(PublicPolicySchema),
        dump_only=True            # solo en output
    )

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)