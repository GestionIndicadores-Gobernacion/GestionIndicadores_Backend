from marshmallow import ValidationError
from models.strategy import Strategy
from models.component import Component
from models.indicator import Indicator
from utils.payload import normalize_payload
import re


def validate_record_payload(data):
    data = normalize_payload(data)

    # ===================================================
    # 1️⃣ Validar STRATEGY
    # ===================================================
    strategy_id = data.get("strategy_id")
    strategy = Strategy.query.get(strategy_id)

    if not strategy:
        raise ValidationError({"strategy_id": "La estrategia indicada no existe."})

    # ===================================================
    # 2️⃣ Validar COMPONENT
    # ===================================================
    component_id = data.get("component_id")
    component = Component.query.get(component_id)

    if not component:
        raise ValidationError({"component_id": "El componente indicado no existe."})

    # Coherencia: componente pertenece a estrategia
    if component.strategy_id != strategy.id:
        raise ValidationError({
            "component_id": (
                "El componente no pertenece a la estrategia seleccionada."
            )
        })

    # ===================================================
    # 5️⃣ detalle_poblacion (diccionario)
    # ===================================================
    detalle = data.get("detalle_poblacion")

    if detalle:
        if not isinstance(detalle, dict):
            raise ValidationError({"detalle_poblacion": "Debe ser un objeto JSON."})

        for k, v in detalle.items():
            if not isinstance(k, str):
                raise ValidationError({"detalle_poblacion": "Las claves deben ser strings."})

            if not isinstance(v, int) or v < 0:
                raise ValidationError({
                    "detalle_poblacion": "Los valores deben ser enteros >= 0."
                })

    # ===================================================
    # 6️⃣ Evidencia URL
    # ===================================================
    evidencia = data.get("evidencia_url")
    if evidencia:
        if not re.match(evidencia.lower()):
            raise ValidationError({
                "evidencia_url": "Debe ser una URL válida"
            })

    return data
