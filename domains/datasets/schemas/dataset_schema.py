from marshmallow import Schema, fields
from domains.datasets.schemas.table_schema import TableSchema


class DatasetSchema(Schema):
    # =========================
    # SOLO LECTURA
    # =========================
    id = fields.Int(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    active = fields.Bool(dump_only=True)

    tables = fields.List(
        fields.Nested(TableSchema),
        dump_only=True
    )

    # =========================
    # INPUT / OUTPUT
    # =========================
    name = fields.Str(required=True)
    description = fields.Str(allow_none=True)
