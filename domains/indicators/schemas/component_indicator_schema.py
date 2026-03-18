from marshmallow import Schema, fields, validate

from domains.indicators.schemas.component_indicator_target_schema import (
    ComponentIndicatorTargetSchema
)

class ComponentIndicatorSchema(Schema):
    id = fields.Int(load_default=None)  # ← cambiar dump_only=True por load_default=None
    
    name = fields.Str(required=True)
    field_type = fields.Str(
        required=True,
        validate=validate.OneOf([
            "number",
            "text",
            "date",
            "select",
            "multi_select",
            "sum_group",
            "grouped_data",
            "file_attachment",
            "categorized_group",
            "dataset_select",
            "dataset_multi_select",
            "red_animalia"
        ])
    )
    config      = fields.Dict(required=False, allow_none=True)
    is_required = fields.Bool(required=False)

    group_name     = fields.Str(allow_none=True, load_default=None)
    group_required = fields.Bool(load_default=False)

    targets = fields.List(
        fields.Nested(ComponentIndicatorTargetSchema),
        required=True
    )

    created_at = fields.DateTime(dump_only=True)