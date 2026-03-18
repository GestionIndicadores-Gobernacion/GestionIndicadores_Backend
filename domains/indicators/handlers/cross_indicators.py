from collections import defaultdict

CROSS_INDICATOR_CONFIG: dict[int, list[tuple]] = {
    24: [(116, 117, -6001, "Cantidad de jóvenes inscritos / institución educativa")],
    25: [(120, 121, -8001, "Temas tratados / foros")],
    26: [(146, 81, -7002, "Cantidad de personas / experiencia")],  # ← 147 → 81
    23: [(115, 114, -11005, "Niños impactados por rango de edad")],
}
def build_cross_indicators(component_id, reports, report_value_map):
    result = []
    if component_id not in CROSS_INDICATOR_CONFIG:
        return result

    for (text_id, number_id, virtual_id, label) in CROSS_INDICATOR_CONFIG[component_id]:
        bucket: dict[str, float] = defaultdict(float)
        for r in reports:
            vals = report_value_map[r.id]
            nombre = vals.get(text_id)
            amount = vals.get(number_id)
            if isinstance(nombre, str) and nombre.strip() and isinstance(amount, (int, float)):
                bucket[nombre.strip()] += amount

        if bucket:
            result.append({
                "indicator_id": virtual_id,
                "indicator_name": label,
                "field_type": "by_category_cross",
                "by_category": [
                    {"category": cat, "total": round(total, 2)}
                    for cat, total in sorted(bucket.items(), key=lambda x: -x[1])
                ]
            })
    return result

def build_multiselect_cross(reports, select_id, number_id, virtual_id, label):
    """
    Cruce multi_select × number.
    Distribuye el total del indicador numérico entre las opciones del multi_select.
    """
    bucket: dict[str, float] = defaultdict(float)

    for r in reports:
        vals = {iv.indicator_id: iv.value for iv in r.indicator_values}
        opciones = vals.get(select_id)
        cantidad = vals.get(number_id)

        if not isinstance(cantidad, (int, float)):
            continue

        # Solo procesar formato array de texto, ignorar IDs numéricos
        if not isinstance(opciones, list):
            continue

        opciones_texto = [o for o in opciones if isinstance(o, str)]
        if not opciones_texto:
            continue

        # Distribuir la cantidad entre todas las opciones seleccionadas
        por_opcion = cantidad / len(opciones_texto)
        for opcion in opciones_texto:
            bucket[opcion.strip()] += por_opcion

    if not bucket:
        return None

    return {
        "indicator_id": virtual_id,
        "indicator_name": label,
        "field_type": "by_category_cross",
        "by_category": [
            {"category": cat, "total": round(total, 0)}
            for cat, total in sorted(bucket.items(), key=lambda x: -x[1])
        ]
    }