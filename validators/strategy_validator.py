from marshmallow import ValidationError
from utils.payload import normalize_payload

def validate_strategy_payload(data):
    data = normalize_payload(data)

    allowed = {"name", "description", "active"}

    # No permitir campos inventados
    unknown = set(data.keys()) - allowed
    if unknown:
        raise ValidationError({ "error": f"Campos no permitidos: {', '.join(unknown)}" })

    # Validación lógica adicional
    if "active" in data and not isinstance(data["active"], bool):
        raise ValidationError({"active": "El campo 'active' debe ser booleano."})

    # Validación name
    name = data.get("name")
    if not name or not name.strip():
        raise ValidationError({"name": "El nombre es obligatorio."})

    if len(name) < 3:
        raise ValidationError({"name": "El nombre debe tener mínimo 3 caracteres."})

    if len(name) > 150:
        raise ValidationError({"name": "El nombre no puede superar 150 caracteres."})

    # Validación description
    desc = data.get("description")
    if desc and len(desc) > 500:
        raise ValidationError({
            "description": "La descripción no puede superar 500 caracteres."
        })
