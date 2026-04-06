from .formatters import norm, is_yes, is_no, group_similar, make_bars, bar_section, unique_clean
from .classifiers import classify_fields
from .builders import (
    SKIP_YESNO, GUIA_KEYWORDS, COLORS,
    build_kpis, build_gender_donut, build_zona_donut,
    build_guias_section, build_grupos_section,
    build_edad_histogram, build_contact_section,
    build_programs_section, build_animals_section,
    build_presupuesto_kpis, build_presupuesto_ejecucion_bar,
    build_presupuesto_by_grupo, build_presupuesto_by_proyecto,
    build_presupuesto_completeness,
)


def detect_dataset_type(fields) -> str:
    names = {f.name.lower() for f in fields}
    if {"mujer", "hombre", "municipio", "guia_1"}.issubset(names):
        return "personas_capacitadas"
    if {"perros_cantidad", "gatos_cantidad", "tipo_de_vinculacion_dentro_de_la_red_animalia_valle"}.issubset(names):
        return "animales"
    if {"apropiacion_definitiva", "cdp_ejecutado", "presup_disponible"}.issubset(names):
        return "presupuesto"
    return "generico"


def analyze_dataset(fields, records):
    total = len(records)
    if total == 0:
        return {"kpis": [], "sections": [], "total": 0}

    field_values = {f.name: [r.data.get(f.name) for r in records] for f in fields}

    # ── RAMA PRESUPUESTO ──────────────────────────────────────────────────────
    if detect_dataset_type(fields) == "presupuesto":
        kpis = build_presupuesto_kpis(field_values, total)
        sections = []
        s = build_presupuesto_completeness(field_values, total)
        if s: sections.append(s)
        s = build_presupuesto_ejecucion_bar(field_values, total)
        if s: sections.append(s)
        s = build_presupuesto_by_grupo(fields, field_values, total)
        if s: sections.append(s)
        s = build_presupuesto_by_proyecto(fields, field_values, total)
        if s: sections.append(s)
        return {"total": total, "kpis": kpis, "sections": sections}
    # ── FIN RAMA PRESUPUESTO ──────────────────────────────────────────────────

    classified = classify_fields(fields, field_values, total)

    contact_fields = [
        f for f in fields
        if any(k in norm(f.name) for k in {"telefono", "correo", "email", "direccion", "celular"})
    ]

    kpis = build_kpis(classified, fields, field_values, total)
    sections = []

    # 1. Cobertura territorial
    for f in classified["location"][:2]:
        s = bar_section(f, field_values[f.name], total, "Cobertura territorial")
        if s: sections.append(s)

    # 2. Edad → histograma
    edad_fields = [f for f in classified["demographic"] if "edad" in norm(f.name) or f.type == "number"]
    for f in edad_fields:
        s = build_edad_histogram(f, field_values, total)
        if s: sections.append(s)

    # 3. Género → donut
    gender = build_gender_donut(fields, field_values, total)
    if gender: sections.append(gender)

    # 4. Zona → donut
    zona = build_zona_donut(fields, field_values, total)
    if zona: sections.append(zona)

    # 5. Guías → barras consolidadas
    guias = build_guias_section(fields, field_values, total)
    if guias: sections.append(guias)

    # 6. Grupos diferenciales → barras consolidadas
    grupos = build_grupos_section(fields, field_values, total)
    if grupos: sections.append(grupos)

    # 7. Animales
    sections += build_animals_section(fields, field_values, total)

    # 8. Otros sí/no que no sean campos especiales
    for f in classified["yesno"]:
        if norm(f.name) in SKIP_YESNO: continue
        if any(k in norm(f.name) for k in GUIA_KEYWORDS): continue
        vals = field_values[f.name]
        yes = sum(1 for v in vals if is_yes(v))
        no  = sum(1 for v in vals if is_no(v))
        if yes + no < 5: continue
        sections.append({
            "id": f.name,
            "title": f.label.strip(),
            "subtitle": f"{yes} de {total} responden Sí",
            "type": "bar",
            "bars": [
                {"label": "Sí", "value": yes, "pct": round(yes / total * 100, 1), "color": COLORS[0]},
                {"label": "No", "value": no,  "pct": round(no  / total * 100, 1), "color": COLORS[6]},
            ]
        })

    # 9. Programas institucionales
    sections += build_programs_section(classified["program"], field_values, total)

    # 10. Contactabilidad
    sections += build_contact_section(contact_fields, field_values, total)

    # 11. Categóricos extra
    for f in classified["categorical"][:3]:
        if norm(f.name) in SKIP_YESNO: continue
        if any(k in norm(f.name) for k in GUIA_KEYWORDS): continue
        s = bar_section(f, field_values[f.name], total)
        if s: sections.append(s)

    return {"total": total, "kpis": kpis, "sections": sections}