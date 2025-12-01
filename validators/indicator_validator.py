from marshmallow import ValidationError
from models.indicator import Indicator
from utils.payload import normalize_payload

ALLOWED_FIELDS = {
    "component_id",
    "name",
    "description",
    "data_type",
    "active"
}

def validate_indicator_payload(data, indicator_id=None):

    # 🔥 Evitar validación cuando viene un modelo (caso DELETE)
    if not isinstance(data, dict):
        return

    data = normalize_payload(data)

    # 1. Campos desconocidos
    unknown = set(data.keys()) - ALLOWED_FIELDS
    if unknown:
        raise ValidationError({
            "error": f"Campos no permitidos: {', '.join(unknown)}"
        })

    # 2. Boolean
    if "active" in data and not isinstance(data["active"], bool):
        raise ValidationError({
            "active": "El campo 'active' debe ser booleano."
        })

    # 3. Unicidad (name + component)
    if "name" in data and "component_id" in data:
        exists = Indicator.query.filter_by(
            name=data["name"],
            component_id=data["component_id"]
        ).first()

        if exists and exists.id != indicator_id:
            raise ValidationError({
                "name": "Ya existe un indicador con este nombre en este componente."
            })

    return True
