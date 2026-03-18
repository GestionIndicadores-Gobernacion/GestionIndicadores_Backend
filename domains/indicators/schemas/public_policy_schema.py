from marshmallow import Schema, fields


class PublicPolicySchema(Schema):
    id          = fields.Int(dump_only=True)
    code        = fields.Str(required=True)
    description = fields.Str(required=True)
    created_at  = fields.DateTime(dump_only=True)
    updated_at  = fields.DateTime(dump_only=True)