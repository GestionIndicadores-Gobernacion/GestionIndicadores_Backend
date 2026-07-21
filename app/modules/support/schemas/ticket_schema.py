# app/modules/support/schemas/ticket_schema.py
from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.modules.support.models.ticket import TICKET_STATUSES

# Tamaño máximo del data URL de UNA imagen (~6 MB de texto base64 ≈ 4.5 MB de
# imagen). Acotado para no inflar la fila ni reventar MAX_CONTENT_LENGTH.
MAX_IMAGE_DATA_URL_LEN = 6 * 1024 * 1024
# Número máximo de imágenes por mensaje.
MAX_IMAGES_PER_MESSAGE = 8
# Tamaño combinado máximo de todas las imágenes de un mensaje (debe quedar por
# debajo de MAX_CONTENT_LENGTH = 10 MB para no rechazar el request entero).
MAX_IMAGES_TOTAL_LEN = 9 * 1024 * 1024


def _validate_image_data_url(value):
    """Acepta solo data URLs de imagen (data:image/<tipo>;base64,...)."""
    if value is None:
        return
    if not isinstance(value, str) or not value.startswith("data:image/"):
        raise ValidationError("La imagen adjunta no tiene un formato válido.")
    if "base64," not in value:
        raise ValidationError("La imagen adjunta debe venir codificada en base64.")
    if len(value) > MAX_IMAGE_DATA_URL_LEN:
        raise ValidationError("La imagen adjunta es demasiado grande.")


def _validate_images_total(images):
    """Valida el tamaño combinado de una lista de imágenes."""
    if images and sum(len(i or "") for i in images) > MAX_IMAGES_TOTAL_LEN:
        raise ValidationError("Las imágenes adjuntas pesan demasiado en conjunto.")


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
    read_by_admin = fields.Bool(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    # Lista unificada de imágenes (nuevas + legado de una sola imagen).
    images = fields.Function(lambda obj: obj.image_list, dump_only=True)
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
    # Respuestas admin sin leer por el dueño (badge del usuario).
    unread_admin_replies = fields.Method("get_unread", dump_only=True)
    # Mensajes de usuario sin leer por el admin (badge del panel admin).
    unread_user_messages = fields.Method("get_unread_admin", dump_only=True)

    def get_last_preview(self, obj):
        # Preferimos el valor precalculado por el handler (sin N+1). Solo
        # recorremos mensajes como fallback (p. ej. en el detalle de 1 ticket).
        pre = getattr(obj, "_summary_last_preview", None)
        if pre is not None:
            return pre
        if not obj.messages:
            return None
        msg = obj.messages[-1]
        body = (msg.body or "").strip()
        if not body and msg.image_list:
            n = len(msg.image_list)
            return "📷 Imagen adjunta" if n == 1 else f"📷 {n} imágenes adjuntas"
        return body[:140] + ("…" if len(body) > 140 else "")

    def get_unread(self, obj):
        cached = getattr(obj, "_summary_unread_owner", None)
        if cached is not None:
            return cached
        return sum(
            1 for m in obj.messages
            if m.is_admin_reply and not m.read_by_owner
        )

    def get_unread_admin(self, obj):
        cached = getattr(obj, "_summary_unread_admin", None)
        if cached is not None:
            return cached
        return sum(
            1 for m in obj.messages
            if not m.is_admin_reply and not m.read_by_admin
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
    # Soporta una imagen (legado) o varias (nuevo) al crear el ticket.
    screenshot_data_url = fields.Str(
        load_default=None, allow_none=True, validate=_validate_image_data_url
    )
    images = fields.List(
        fields.Str(validate=_validate_image_data_url),
        load_default=list,
        validate=validate.Length(max=MAX_IMAGES_PER_MESSAGE),
    )

    @validates_schema
    def _images_total(self, data, **kwargs):
        _validate_images_total(data.get("images"))


class AddMessageSchema(Schema):
    # body deja de ser obligatorio: un mensaje puede ser solo imágenes.
    # validates_schema garantiza que venga al menos texto o una imagen.
    body = fields.Str(
        load_default="",
        validate=validate.Length(max=4000),
    )
    # Compat: una sola imagen. Nuevo: lista de imágenes.
    image_data_url = fields.Str(
        load_default=None, allow_none=True, validate=_validate_image_data_url
    )
    images = fields.List(
        fields.Str(validate=_validate_image_data_url),
        load_default=list,
        validate=validate.Length(max=MAX_IMAGES_PER_MESSAGE),
    )

    @validates_schema
    def _at_least_one(self, data, **kwargs):
        has_image = bool(data.get("images")) or bool(data.get("image_data_url"))
        if not (data.get("body") or "").strip() and not has_image:
            raise ValidationError(
                "Escribe un mensaje o adjunta una imagen.", field_name="body"
            )
        _validate_images_total(data.get("images"))


class UpdateTicketStatusSchema(Schema):
    status = fields.Str(
        required=True,
        validate=validate.OneOf(TICKET_STATUSES),
    )
