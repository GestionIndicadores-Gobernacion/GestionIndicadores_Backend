from domains.datasets.models.field import Field
from domains.utils.inference import infer_field_type
from domains.utils.normalizers import normalize_name
from extensions import db


def create_fields(table, df):
    field_map = {}
    existing = set()

    for column in df.columns:
        base = normalize_name(column)
        name = base
        i = 1

        while name in existing:
            name = f"{base}_{i}"
            i += 1

        existing.add(name)

        field = Field(
            table_id=table.id,
            name=name,
            label=str(column),
            type=infer_field_type(df[column]),
            required=False
        )

        db.session.add(field)
        field_map[column] = name

    db.session.flush()
    return field_map
