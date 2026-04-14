from app.modules.datasets.models.field import Field
from app.utils.inference import infer_field_type
from app.utils.normalizers import normalize_name
from app.core.extensions import db


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
            label=str(column).strip()[:500],
            type=infer_field_type(df[column]),
            required=False
        )

        db.session.add(field)
        field_map[column] = name

    db.session.flush()
    return field_map
