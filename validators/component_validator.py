from marshmallow import ValidationError
from models.component import Component
from utils.payload import normalize_payload

ALLOWED_FIELDS = {"strategy_id", "name", "description", "data_type", "active"}

def validate_component_payload(data, component_id=None):
    data = normalize_payload(data)

    # Evitar campos inventados
    unknown = set(data.keys()) - ALLOWED_FIELDS
    if unknown:
        raise ValidationError({"error": f"Campos no permitidos: {', '.join(unknown)}"})

    # Validar boolean
    if "active" in data and not isinstance(data["active"], bool):
        raise ValidationError({"active": "El campo 'active' debe ser booleano."})

    # Validación de unicidad (nombre + strategy)
    if "name" in data and "strategy_id" in data:
        exists = Component.query.filter_by(
            name=data["name"],
            strategy_id=data["strategy_id"]
        ).first()

        if exists and exists.id != component_id:
            raise ValidationError({
                "name": "Ya existe un componente con este nombre para esta estrategia."
            })
