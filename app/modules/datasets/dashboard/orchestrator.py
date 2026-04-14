from .builders.generico import build_generico
from .builders.presupuesto import build_presupuesto
from .builders.censo_animal import build_censo_animal


def orchestrate(dtype: str, fields, field_values, total) -> dict:
    if dtype == "presupuesto":
        return build_presupuesto(fields, field_values, total)

    if dtype == "censo_animal":
        return build_censo_animal(fields, field_values, total)

    # generico, personas_capacitadas, animales → pipeline genérico
    return build_generico(fields, field_values, total)