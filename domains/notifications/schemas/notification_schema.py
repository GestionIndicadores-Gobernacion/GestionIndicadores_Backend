# domains/notifications/schemas/notification_schema.py
from marshmallow import Schema, fields


class NotificationSchema(Schema):
    id = fields.Int(dump_only=True)
    user_id = fields.Int(dump_only=True)
    title = fields.Str(dump_only=True)
    message = fields.Str(dump_only=True)
    category = fields.Str(dump_only=True)
    entity_id = fields.Int(dump_only=True, allow_none=True)
    is_read = fields.Bool(dump_only=True)
    read_at = fields.DateTime(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)