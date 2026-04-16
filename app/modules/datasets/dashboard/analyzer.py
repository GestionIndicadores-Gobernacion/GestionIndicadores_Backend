from .orchestrator import orchestrate


def detect_dataset_type(fields) -> str:
    names = {f.name.lower() for f in fields}
    if {"mujer", "hombre", "municipio", "guia_1"}.issubset(names):
        return "personas_capacitadas"
    # Red Animalia: tiene vinculación + campos de animales domésticos
    if ("tipo_de_vinculacion_dentro_de_la_red_animalia_valle" in names
            and any("perros" in n for n in names)
            and any("gatos" in n for n in names)):
        return "red_animalia"
    if ({"perros_cantidad", "gatos_cantidad",
         "tipo_de_vinculacion_dentro_de_la_red_animalia_valle"}.issubset(names) or
            {"nombres_y_apellidos", "municipio", "otro_telefono",
             "correo_electronico"}.issubset(names)):
        return "animales"
    if ({"apropiacion_definitiva", "presup_disponible"}.issubset(names) and
            ("cdp_ejecutado" in names or "total_ejecutado" in names)):
        return "presupuesto"
    if {"poblacion_perros_2026", "poblacion_gatos_2026", "municipio"}.issubset(names):
        return "censo_animal"
    if "municipio" in names and any("perros" in n for n in names) and any("gatos" in n for n in names):
        return "censo_animal"
    return "generico"


def analyze_dataset(fields, records) -> dict:
    total = len(records)
    if total == 0:
        return {"kpis": [], "sections": [], "total": 0}

    field_values = {f.name: [r.data.get(f.name) for r in records] for f in fields}
    dtype = detect_dataset_type(fields)

    result = orchestrate(dtype, fields, field_values, total)
    result["dataset_type"] = dtype
    return result