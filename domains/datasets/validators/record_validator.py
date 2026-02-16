from marshmallow import ValidationError
from domains.datasets.models.table import Table
from domains.datasets.models.field import Field
from domains.datasets.validators.field_type_validator import _validate_field_type


def validate_record_data(table: Table, data: dict):
    """
    Valida que el data del record cumpla con la estructura de la tabla
    """

    if not isinstance(data, dict):
        raise ValidationError({"data": "El campo data debe ser un objeto JSON"})

    fields = {field.name: field for field in table.fields}

    # 1️⃣ Campos obligatorios
    for field in fields.values():
        if field.required and field.name not in data:
            raise ValidationError({
                field.name: f"El campo '{field.label}' es obligatorio"
            })

    # 2️⃣ Campos inexistentes
    for key in data.keys():
        if key not in fields:
            raise ValidationError({
                key: "Este campo no existe en la estructura de la tabla"
            })

    # 3️⃣ Validar tipo de dato
    for name, value in data.items():
        field = fields[name]
        _validate_field_type(field, value)
