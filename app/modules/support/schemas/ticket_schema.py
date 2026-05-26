# app/modules/support/schemas/ticket_schema.py
from marshmallow import Schema, fields, validate

from app.modules.support.models.ticket import TICKET_STATUSES


class TicketAuthorSchema(Schema):
    """Subset de campos del autor expuestos en el ticket / mensaje."""
    id = fields.Int(dump_only=True)
    first_name = fields.Str(dump_only=True)
    last_name = fields.Str(dump_only=True)
    email = fields.Str(dump_only=True)
    role = fields.Method("get_role", dump_only=True)

    def get_role(self, obj):
        return obj.role.name if obj and obj.role else None


class SupportMessageSchema(Schema):
    id = fields.Int(dump_only=True)
    ticket_id = fields.Int(dump_only=True)
    body = fields.Str(dump_only=True)
    is_admin_reply = fields.Bool(dump_only=True)
    read_by_owner = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    author = fields.Nested(TicketAuthorSchema, attribute="user", dump_only=True)


class SupportTicketSummarySchema(Schema):
    """Vista compacta para listados (sin los mensajes)."""
    id = fields.Int(dump_only=True)
    title = fields.Str(dump_only=True)
    status = fields.Str(dump_only=True)
    current_url = fields.Str(dump_only=True, allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    author = fields.Nested(TicketAuthorSchema, attribute="user", dump_only=True)
    last_message_preview = fields.Method("get_last_preview", dump_only=True)
    unread_admin_replies = fields.Method("get_unread", dump_only=True)

    def get_last_preview(self, obj):
        if not obj.messages:
            return None
        msg = obj.messages[-1]
        body = msg.body or ""
        return body[:140] + ("…" if len(body) > 140 else "")

    def get_unread(self, obj):
        return sum(
            1 for m in obj.messages
            if m.is_admin_reply and not m.read_by_owner
        )


class SupportTicketDetailSchema(SupportTicketSummarySchema):
    user_agent = fields.Str(dump_only=True, allow_none=True)
    messages = fields.Nested(SupportMessageSchema, many=True, dump_only=True)


class CreateTicketSchema(Schema):
    message = fields.Str(
        required=True,
        validate=validate.Length(min=10, max=4000),
    )
    current_url = fields.Str(load_default="", validate=validate.Length(max=1000))
    user_agent = fields.Str(load_default="", validate=validate.Length(max=500))
    screenshot_data_url = fields.Str(load_default=None, allow_none=True)


class AddMessageSchema(Schema):
    body = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=4000),
    )


class UpdateTicketStatusSchema(Schema):
    status = fields.Str(
        required=True,
        validate=validate.OneOf(TICKET_STATUSES),
    )
