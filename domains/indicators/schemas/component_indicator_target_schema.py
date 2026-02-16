from marshmallow import Schema, fields


class ComponentIndicatorTargetSchema(Schema):
    id = fields.Int(dump_only=True)

    year = fields.Int(required=True)
    target_value = fields.Float(required=True)

    created_at = fields.DateTime(dump_only=True)
