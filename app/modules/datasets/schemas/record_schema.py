from marshmallow import Schema, fields


class RecordSchema(Schema):
    # =========================
    # SOLO LECTURA
    # =========================
    id = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)

    # =========================
    # INPUT / OUTPUT
    # =========================
    table_id = fields.Int(required=True)
    data = fields.Dict(required=True)
