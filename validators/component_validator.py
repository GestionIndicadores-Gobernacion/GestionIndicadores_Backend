from marshmallow import ValidationError
from models.component import Component
from utils.payload import normalize_payload

ALLOWED_FIELDS = {"activity_id", "name", "description", "data_type", "active"}

def validate_component_payload(data, component_id=None):

    # Instancia SQLAlchemy → no validar
    if hasattr(data, "_sa_instance_state"):
        return

    if not isinstance(data, dict):
        return

    data = normalize_payload(data)

    # Campos desconocidos
    unknown = set(data.keys()) - ALLOWED_FIELDS
    if unknown:
        raise ValidationError({
            "error": f"Campos no permitidos: {', '.join(unknown)}"
        })

    # Active
    if "active" in data and not isinstance(data["active"], bool):
        raise ValidationError({
            "active": "El campo 'active' debe ser booleano."
        })

    # Unicidad: nombre + actividad
    if "name" in data and "activity_id" in data:
        exists = Component.query.filter_by(
            name=data["name"],
            activity_id=data["activity_id"]
        ).first()

        if exists and exists.id != component_id:
            raise ValidationError({
                "name": "Ya existe un componente con este nombre para esta actividad."
            })

    return True
