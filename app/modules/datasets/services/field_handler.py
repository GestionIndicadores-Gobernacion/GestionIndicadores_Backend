from app.modules.datasets.models.field import Field
from app.utils.inference import infer_field_type
from app.utils.normalizers import normalize_name
from app.core.extensions import db


def plan_field_names(columns) -> dict:
    """
    Mapa columna del Excel → ``Field.name`` que se va a crear
    (``normalize_name`` + sufijo ``_1``, ``_2``... para duplicados).

    Se usa tanto para crear los campos como para validar compatibilidad del
    Excel antes de escribir en la base, así ambos ven exactamente los mismos
    nombres.
    """
    field_map = {}
    existing = set()

    for column in columns:
        base = normalize_name(column)
        name = base
        i = 1

        while name in existing:
            name = f"{base}_{i}"
            i += 1

        existing.add(name)
        field_map[column] = name

    return field_map


def create_fields(table, df):
    field_map = plan_field_names(df.columns)

    for column, name in field_map.items():
        field = Field(
            table_id=table.id,
            name=name,
            label=str(column).strip()[:500],
            type=infer_field_type(df[column]),
            required=False
        )
        db.session.add(field)

    db.session.flush()
    return field_map
