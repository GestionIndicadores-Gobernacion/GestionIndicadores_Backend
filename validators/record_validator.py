from models.strategy import Strategy
from models.component import Component
from models.activity import Activity
from utils.payload import normalize_payload
from marshmallow import ValidationError
import re

def validate_record_payload(data):
    data = normalize_payload(data)

    # ===============================
    # 1. STRATEGY
    # ===============================
    strategy_id = data.get("strategy_id")
    strategy = Strategy.query.get(strategy_id)

    if not strategy:
        raise ValidationError({"strategy_id": "La estrategia indicada no existe."})

    # ===============================
    # 2. ACTIVITY
    # ===============================
    activity_id = data.get("activity_id")
    activity = Activity.query.get(activity_id)

    if not activity:
        raise ValidationError({"activity_id": "La actividad indicada no existe."})

    if activity.strategy_id != strategy.id:
        raise ValidationError({
            "activity_id": "La actividad no pertenece a la estrategia seleccionada."
        })

    # ===============================
    # 3. COMPONENT
    # ===============================
    component_id = data.get("component_id")
    component = Component.query.get(component_id)

    if not component:
        raise ValidationError({"component_id": "El componente indicado no existe."})

    if component.strategy_id != strategy.id:
        raise ValidationError({
            "component_id": "El componente no pertenece a la estrategia seleccionada."
        })

    # ===============================
    # 4. DETALLE POBLACIÓN
    # ===============================
    detalle = data.get("detalle_poblacion")

    if not detalle:
        raise ValidationError({"detalle_poblacion": "Este campo es obligatorio."})

    if not isinstance(detalle, dict):
        raise ValidationError({"detalle_poblacion": "Debe ser un objeto JSON válido."})

    if "municipios" not in detalle:
        raise ValidationError({"detalle_poblacion": "Debe incluir 'municipios'."})

    municipios = detalle["municipios"]

    if not isinstance(municipios, dict):
        raise ValidationError({"detalle_poblacion": "'municipios' debe ser un diccionario."})

    # DESCRIPTION
    desc = data.get("description")
    if desc and len(desc) > 500:
        raise ValidationError({"description": "La descripción no puede superar 500 caracteres."})

    # Validar municipios e indicadores
    for municipio, info in municipios.items():

        if not isinstance(municipio, str) or not municipio.strip():
            raise ValidationError({
                "detalle_poblacion": f"El nombre de municipio '{municipio}' es inválido."
            })

        if not isinstance(info, dict) or "indicadores" not in info:
            raise ValidationError({
                "detalle_poblacion": f"El municipio '{municipio}' debe contener 'indicadores'."
            })

        indicadores = info["indicadores"]

        if not isinstance(indicadores, dict):
            raise ValidationError({
                "detalle_poblacion": f"'indicadores' en '{municipio}' debe ser un diccionario."
            })

        for indicador, valor in indicadores.items():
            if not isinstance(valor, int) or valor < 0:
                raise ValidationError({
                    "detalle_poblacion": (
                        f"El valor de '{indicador}' en '{municipio}' debe ser un entero >= 0."
                    )
                })

    # ===============================
    # 5. URL
    # ===============================
    evidencia = data.get("evidencia_url")
    if evidencia:
        pattern = r"^https?:\/\/[\w\-\.\/\?\=\&\#%]+$"
        if not re.match(pattern, evidencia):
            raise ValidationError({"evidencia_url": "Debe ser una URL válida."})

    return data
