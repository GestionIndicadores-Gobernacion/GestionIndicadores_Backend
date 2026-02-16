from marshmallow import Schema, fields
from domains.datasets.schemas.field_schema import FieldSchema


class TableSchema(Schema):
    # =========================
    # SOLO LECTURA
    # =========================
    id = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    active = fields.Bool(dump_only=True)

    table_fields = fields.List(
        fields.Nested(FieldSchema),
        dump_only=True
    )

    # =========================
    # INPUT / OUTPUT
    # =========================
    dataset_id = fields.Int(required=True)
    name = fields.Str(required=True)
    description = fields.Str(allow_none=True)
