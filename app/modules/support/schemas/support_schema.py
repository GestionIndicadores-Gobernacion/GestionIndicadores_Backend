# app/modules/support/schemas/support_schema.py
from marshmallow import Schema, fields, validate


class SupportReportSchema(Schema):
    """Payload del botón flotante 'Reportar fallo'."""

    message = fields.Str(
        required=True,
        validate=validate.Length(min=10, max=4000),
        metadata={"description": "Descripción libre del problema (10–4000 chars)."},
    )
    current_url = fields.Str(
        load_default="",
        validate=validate.Length(max=1000),
    )
    user_agent = fields.Str(
        load_default="",
        validate=validate.Length(max=500),
    )
    # Captura opcional en data-URL (image/png o image/jpeg en base64).
    # Aceptamos hasta ~5 MB de payload entrante (validado en la ruta).
    screenshot_data_url = fields.Str(
        load_default=None,
        allow_none=True,
    )
