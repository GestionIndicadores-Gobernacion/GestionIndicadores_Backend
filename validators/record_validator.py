from models.component import Component
from marshmallow import ValidationError
import re

def validate_record_payload(record):

    # ===============================
    # 1️⃣ COMPONENTE (único input real)
    # ===============================
    component = Component.query.get(record.component_id)

    if not component:
        raise ValidationError({"component_id": "El componente no existe."})

    activity = component.activity
    if not activity:
        raise ValidationError({"component_id": "El componente no tiene actividad asociada."})

    strategy = activity.strategy
    if not strategy:
        raise ValidationError({"component_id": "La actividad no tiene estrategia asociada."})

    # 🔥 ASIGNACIÓN DERIVADA
    record.activity_id = activity.id
    record.strategy_id = strategy.id

    # ===============================
    # 2️⃣ VALIDAR DESCRIPCIONES
    # ===============================
    if record.description and len(record.description) > 500:
        raise ValidationError({"description": "Máximo 500 caracteres."})

    if record.actividades_realizadas and len(record.actividades_realizadas) > 2000:
        raise ValidationError({"actividades_realizadas": "Máximo 2000 caracteres."})

    # ===============================
    # 3️⃣ DETALLE POBLACIÓN
    # ===============================
    detalle = record.detalle_poblacion

    if not isinstance(detalle, dict) or "municipios" not in detalle:
        raise ValidationError({"detalle_poblacion": "Debe incluir municipios."})

    for municipio, info in detalle["municipios"].items():
        if "indicadores" not in info or not isinstance(info["indicadores"], dict):
            raise ValidationError({
                "detalle_poblacion": f"Municipio '{municipio}' mal estructurado."
            })

        for valor in info["indicadores"].values():
            if not isinstance(valor, int) or valor < 0:
                raise ValidationError({
                    "detalle_poblacion": "Los valores deben ser enteros >= 0."
                })

    # ===============================
    # 4️⃣ URL
    # ===============================
    if record.evidencia_url:
        pattern = r"^https?:\/\/[\w\-\.\/\?\=\&\#%]+$"
        if not re.match(pattern, record.evidencia_url):
            raise ValidationError({"evidencia_url": "URL inválida."})

    return record
