from marshmallow import Schema, fields, validate

class FieldSchema(Schema):
    # =========================
    # SOLO LECTURA
    # =========================
    id = fields.Int(dump_only=True)

    # =========================
    # INPUT / OUTPUT
    # =========================
    table_id = fields.Int(required=True)

    name = fields.Str(required=True)
    label = fields.Str(required=True)

    type = fields.Str(
        required=True,
        validate=validate.OneOf(
            ["text", "number", "select", "boolean", "date"]
        )
    )

    required = fields.Bool(load_default=False)
    options = fields.List(fields.Raw(), allow_none=True)
