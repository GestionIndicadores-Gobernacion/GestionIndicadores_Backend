from marshmallow import Schema, fields


class AuditLogSchema(Schema):
    id         = fields.Int(dump_only=True)
    user_id    = fields.Int(allow_none=True)
    entity     = fields.Str()
    entity_id  = fields.Int()
    action     = fields.Str()
    detail     = fields.Str(allow_none=True)
    created_at = fields.DateTime(dump_only=True, format='iso')