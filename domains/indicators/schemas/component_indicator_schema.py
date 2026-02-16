from marshmallow import Schema, fields
from domains.indicators.schemas.component_indicator_target_schema import (
    ComponentIndicatorTargetSchema
)


class ComponentIndicatorSchema(Schema):
    id = fields.Int(dump_only=True)

    name = fields.Str(required=True)
    field_type = fields.Str(required=True)
    config = fields.Dict(required=False, allow_none=True)
    is_required = fields.Bool(required=False)

    targets = fields.List(
        fields.Nested(ComponentIndicatorTargetSchema),
        required=True
    )

    created_at = fields.DateTime(dump_only=True)
