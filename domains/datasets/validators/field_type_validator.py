from marshmallow import ValidationError
from datetime import date

from domains.datasets.models.field import Field

def _validate_field_type(field: Field, value):
    field_type = field.type

    if field_type == "text":
        if not isinstance(value, str):
            raise ValidationError({field.name: "Debe ser texto"})

    elif field_type == "number":
        if not isinstance(value, (int, float)):
            raise ValidationError({field.name: "Debe ser numérico"})
    
    elif field_type == "boolean":
        if not isinstance(value, bool):
            raise ValidationError({field.name: "Debe ser booleano"})

    elif field_type == "date":
        if not isinstance(value, str):
            raise ValidationError({
                field.name: "Debe ser una fecha en formato YYYY-MM-DD"
            })

    elif field_type == "select":
        options = field.options or []
        if value not in options:
            raise ValidationError({
                field.name: f"Valor inválido. Opciones permitidas: {options}"
            })
