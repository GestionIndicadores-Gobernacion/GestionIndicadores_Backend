from marshmallow import ValidationError
from utils.payload import normalize_payload

def validate_activity_payload(data):

    # Instancia SQLAlchemy → no validar
    if hasattr(data, "_sa_instance_state"):
        return

    if not isinstance(data, dict):
        return

    data = normalize_payload(data)
    allowed = {"strategy_id", "description", "active"}

    unknown = set(data.keys()) - allowed
    if unknown:
        raise ValidationError({"error": f"Campos no permitidos: {', '.join(unknown)}"})

    # Strategy
    if "strategy_id" not in data:
        raise ValidationError({"strategy_id": "Debe especificar la estrategia."})

    # Active (opcional)
    if "active" in data and not isinstance(data["active"], bool):
        raise ValidationError({"active": "El campo 'active' debe ser booleano."})

    # Description (obligatoria)
    desc = data.get("description")
    if not desc or not desc.strip():
        raise ValidationError({"description": "La descripción es obligatoria."})

    if len(desc) < 3:
        raise ValidationError({"description": "Debe tener mínimo 3 caracteres."})

    if len(desc) > 500:
        raise ValidationError({"description": "La descripción no puede superar 500 caracteres."})
