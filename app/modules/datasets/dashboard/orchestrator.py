from .builders.generico import build_generico
from .builders.presupuesto import build_presupuesto
from .builders.censo_animal import build_censo_animal
from .builders.donaton import build_donaton
from .builders.denuncias import build_denuncias


def orchestrate(dtype: str, fields, field_values, total) -> dict:
    if dtype == "presupuesto":
        return build_presupuesto(fields, field_values, total)

    if dtype == "censo_animal":
        return build_censo_animal(fields, field_values, total)

    if dtype == "donaton":
        return build_donaton(fields, field_values, total)

    if dtype == "denuncias":
        return build_denuncias(fields, field_values, total)

    # generico, personas_capacitadas, animales, red_animalia → pipeline genérico
    return build_generico(fields, field_values, total)
