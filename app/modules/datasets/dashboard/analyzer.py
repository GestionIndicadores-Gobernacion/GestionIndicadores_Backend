from .orchestrator import orchestrate


def detect_dataset_type(fields, name_hint: str = "") -> str:
    # Regla de máxima prioridad por nombre: cualquier archivo/dataset "Z080"
    # es el reporte presupuestal (Z080 es el código del informe de ejecución
    # presupuestal). Se evalúa antes que la detección por columnas porque el
    # formato del Excel puede variar entre cortes mensuales (columnas vacías
    # descartadas por el filtro de relleno, encabezados distintos, etc.) y
    # aun así debe renderizar la vista de presupuesto.
    if "z080" in (name_hint or "").lower():
        return "presupuesto"

    names = {f.name.lower() for f in fields}
    # Denuncias: caso + denunciante + motivo de la denuncia (texto largo).
    # Se evalúa primero porque el Excel puede traer también "municipio" y
    # "fecha", que entrarían en colisión con otros tipos.
    if (
        any("numero_de_caso" in n or n == "numero_de_caso" for n in names)
        and any("denunciante" in n for n in names)
        and any("motivo" in n for n in names)
    ):
        return "denuncias"
    # Donatón: hay alimento perro/gato + municipio + total (kg recogidos).
    # Detectado antes de personas_capacitadas porque también tiene
    # "municipio" pero no entra en colisión por los demás campos.
    if (
        "municipio" in names
        and any("alimento" in n and "perro" in n for n in names)
        and any("alimento" in n and "gato" in n for n in names)
    ):
        return "donaton"
    # Personas capacitadas (formato consolidado 2026): además de las guías 1/2/3
    # incluye fecha, rural/urbana, correo_electronico y observacion.
    if {"mujer", "hombre", "municipio", "guia_1", "guia_2", "guia_3",
        "rural", "urbana", "fecha"}.issubset(names):
        return "personas_capacitadas_consolidado"
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


def analyze_dataset(fields, records, name_hint: str = "") -> dict:
    total = len(records)
    if total == 0:
        return {"kpis": [], "sections": [], "total": 0}

    field_values = {f.name: [r.data.get(f.name) for r in records] for f in fields}
    dtype = detect_dataset_type(fields, name_hint)

    result = orchestrate(dtype, fields, field_values, total)
    result["dataset_type"] = dtype
    return result