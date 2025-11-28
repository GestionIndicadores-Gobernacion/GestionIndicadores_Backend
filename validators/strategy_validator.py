from marshmallow import ValidationError
from utils.payload import normalize_payload

def validate_strategy_payload(data):

    # 🔥 Evitar validación cuando data es un modelo SQLAlchemy (DELETE)
    if hasattr(data, "_sa_instance_state"):
        return

    # O si no es dict, también ignorar
    if not isinstance(data, dict):
        return

    data = normalize_payload(data)
    allowed = {"name", "description", "active"}

    unknown = set(data.keys()) - allowed
    if unknown:
        raise ValidationError({"error": f"Campos no permitidos: {', '.join(unknown)}"})

    if "active" in data and not isinstance(data["active"], bool):
        raise ValidationError({"active": "El campo 'active' debe ser booleano."})

    name = data.get("name")
    if not name or not name.strip():
        raise ValidationError({"name": "El nombre es obligatorio."})

    if len(name) < 3:
        raise ValidationError({"name": "El nombre debe tener mínimo 3 caracteres."})

    if len(name) > 150:
        raise ValidationError({"name": "El nombre no puede superar 150 caracteres."})

    desc = data.get("description")
    if desc and len(desc) > 500:
        raise ValidationError({
            "description": "La descripción no puede superar 500 caracteres."
        })
