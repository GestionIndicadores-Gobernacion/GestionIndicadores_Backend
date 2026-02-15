from marshmallow import Schema, fields
from domains.indicators.schemas.component_objective_schema import ComponentObjectiveSchema
from domains.indicators.schemas.component_mga_activity_schema import ComponentMGAActivitySchema
from domains.indicators.schemas.component_indicator_schema import ComponentIndicatorSchema


class ComponentSchema(Schema):

    id = fields.Int(dump_only=True)
    strategy_id = fields.Int(required=True)
    name = fields.Str(required=True)

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

    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
