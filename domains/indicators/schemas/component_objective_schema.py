from marshmallow import Schema, fields


class ComponentObjectiveSchema(Schema):
    id = fields.Int(dump_only=True)
    description = fields.Str(required=True)
