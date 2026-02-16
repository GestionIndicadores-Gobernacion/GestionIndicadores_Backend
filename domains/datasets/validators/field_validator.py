from marshmallow import ValidationError
from domains.datasets.models.field import Field
from extensions import db


ALLOWED_TYPES = {"text", "number", "select", "boolean", "date"}


def validate_field_definition(
    *,
    name: str,
    label: str,
    field_type: str,
    table_id: int,
    options: list | None = None,
    field_id: int | None = None
):
    """
    Valida reglas de negocio de un Field
    """

    # 1️⃣ name obligatorio
    if not name or not name.strip():
        raise ValidationError({"name": "El nombre del campo es obligatorio"})

    # 2️⃣ label obligatorio
    if not label or not label.strip():
        raise ValidationError({"label": "La etiqueta del campo es obligatoria"})

    # 3️⃣ type válido
    if field_type not in ALLOWED_TYPES:
        raise ValidationError({
            "type": f"Tipo inválido. Opciones: {list(ALLOWED_TYPES)}"
        })

    # 4️⃣ name único dentro de la tabla
    query = Field.query.filter(
        Field.table_id == table_id,
        db.func.lower(Field.name) == name.lower()
    )

    if field_id:
        query = query.filter(Field.id != field_id)

    if query.first():
        raise ValidationError({
            "name": "Ya existe un campo con este nombre en la tabla"
        })

    # 5️⃣ reglas de options según type
    if field_type == "select":
        if not options or not isinstance(options, list):
            raise ValidationError({
                "options": "El campo select requiere una lista de opciones"
            })

        if len(options) == 0:
            raise ValidationError({
                "options": "Debe definir al menos una opción"
            })
    else:
        if options:
            raise ValidationError({
                "options": "Este tipo de campo no admite opciones"
            })
