import re
from ..formatters import (
    COLORS, norm, is_yes, is_no, fill_rate,
    group_similar, make_bars, bar_section,
    numeric_bins, numeric_stats, unique_clean
)
from ..classifiers import classify_fields
from .shared import (
    SKIP_YESNO, GUIA_KEYWORDS, ANIMAL_KW,
    GENDER_FIELDS, ZONA_FIELDS, GRUPOS_FIELDS,
    _global_fill_rate
)


# ─── KPIs ─────────────────────────────────────────────────────────────────────

def build_kpis(classified, all_fields, field_values, total):
    kpis = [{"label": "Total registros", "value": str(total), "icon": "users"}]

    for f in classified.get("location", []):
        n = len(unique_clean(field_values[f.name]))
        kpis.append({"label": f"{f.label.strip()} con presencia", "value": str(n), "icon": "map"})

    for f in classified.get("program", [])[:4]:
        vals = field_values[f.name]
        p = sum(1 for v in vals if v is not None and str(v).strip() and norm(v) not in ("no", "0", "0.0", ""))
        year_match = re.search(r'(20\d{2})', f.name)
        label = f.label.strip()[:25]
        if year_match:
            label = f"{label} {year_match.group(1)}"
        kpis.append({
            "label": label,
            "value": str(p),
            "sub": f"{round(p / total * 100)}% del total",
            "icon": "check"
        })

    for f in all_fields:
        if any(k in norm(f.name) for k in ANIMAL_KW) and f.type == "number":
            stats = numeric_stats(field_values[f.name])
            if stats and stats["count"] > 0:
                kpis.append({
                    "label": f"Total {f.label.strip()}",
                    "value": f"{int(stats['total']):,}",
                    "sub": f"{stats['count']} con datos",
                    "icon": "number"
                })

    return kpis[:7]


# ─── Secciones ────────────────────────────────────────────────────────────────

def build_gender_donut(fields, field_values, total):
    labels = {
        "mujer":       ("Mujer",       "#DB2777"),
        "hombre":      ("Hombre",      "#2563EB"),
        "intersesual": ("Intersexual", "#7C3AED"),
        "lgbtiq_":     ("LGBTIQ+",     "#0891B2"),
    }
    segments = []
    accounted = 0
    for fname, (label, color) in labels.items():
        f = next((x for x in fields if norm(x.name) == fname), None)
        if not f: continue
        count = sum(1 for v in field_values[f.name] if is_yes(v))
        if count == 0: continue
        accounted += count
        segments.append({"label": label, "value": count,
                          "pct": round(count / total * 100, 1), "color": color})
    if not segments: return None
    sin_registro = total - accounted
    if sin_registro > 0:
        segments.append({"label": "Sin registro", "value": sin_registro,
                          "pct": round(sin_registro / total * 100, 1), "color": "#E2E8F0"})
    return {
        "id": "__gender__", "title": "Distribución por género",
        "subtitle": f"{accounted} de {total} con género registrado",
        "type": "donut", "segments": segments,
    }


def build_zona_donut(fields, field_values, total):
    labels = {
        "rural":  ("Rural",  "#059669"),
        "urbana": ("Urbana", "#2563EB"),
    }
    segments = []
    accounted = 0
    for fname, (label, color) in labels.items():
        f = next((x for x in fields if norm(x.name) == fname), None)
        if not f: continue
        count = sum(1 for v in field_values[f.name] if is_yes(v))
        if count == 0: continue
        accounted += count
        segments.append({"label": label, "value": count,
                          "pct": round(count / total * 100, 1), "color": color})
    if not segments: return None
    sin_registro = total - accounted
    if sin_registro > 0:
        segments.append({"label": "Sin registro", "value": sin_registro,
                          "pct": round(sin_registro / total * 100, 1), "color": "#E2E8F0"})
    return {
        "id": "__zona__", "title": "Zona de residencia",
        "subtitle": f"Rural vs Urbana · {total} registros",
        "type": "donut", "segments": segments,
    }


def build_guias_section(fields, field_values, total):
    guia_fields = [
        f for f in fields
        if any(k in norm(f.name) for k in GUIA_KEYWORDS)
        and norm(f.name) not in {"municipio", "mes"}
    ]
    if not guia_fields: return None
    colors = ["#2563EB", "#0891B2", "#059669", "#7C3AED"]
    bars = []
    for i, f in enumerate(guia_fields):
        count = sum(1 for v in field_values[f.name] if is_yes(v))
        if count == 0: continue
        bars.append({"label": f.label.strip(), "value": count,
                      "pct": round(count / total * 100, 1), "color": colors[i % len(colors)]})
    if not bars: return None
    return {
        "id": "__guias__", "title": "Participación por guía",
        "subtitle": f"{len(bars)} guías registradas",
        "type": "bar", "bars": bars,
    }


def build_grupos_section(fields, field_values, total):
    GRUPOS = {
        "afro":          ("Afrodescendiente", "#D97706"),
        "indigena":      ("Indígena",         "#059669"),
        "rrom":          ("RROM",             "#7C3AED"),
        "discapacidad":  ("Discapacidad",     "#0891B2"),
        "victima":       ("Víctima",          "#DC2626"),
        "reincorporado": ("Reincorporado",    "#DB2777"),
    }
    bars = []
    for fname, (label, color) in GRUPOS.items():
        f = next((x for x in fields if norm(x.name) == fname), None)
        if not f: continue
        count = sum(1 for v in field_values[f.name] if is_yes(v))
        bars.append({"label": label, "value": count,
                      "pct": round(count / total * 100, 1), "color": color})
    bars = sorted([b for b in bars if b["value"] > 0], key=lambda x: -x["value"])
    if not bars: return None
    return {
        "id": "__grupos__", "title": "Grupos diferenciales",
        "subtitle": "Población con enfoque diferencial",
        "type": "bar", "bars": bars,
    }


def build_edad_histogram(field, field_values, total):
    vals = field_values[field.name]
    bins = numeric_bins(vals)
    stats = numeric_stats(vals)
    if not bins: return None
    return {
        "id": field.name, "title": field.label.strip(),
        "subtitle": f"Distribución por rangos · Promedio: {stats.get('avg', 0)} años",
        "type": "histogram", "bars": bins,
    }


def build_contact_section(fields, field_values, total):
    bars = []
    for f in fields:
        rate = fill_rate(field_values[f.name], total)
        bars.append({
            "label": f.label.strip(), "value": round(rate), "pct": rate,
            "color": COLORS[0] if rate >= 80 else COLORS[2] if rate >= 50 else COLORS[6]
        })
    if not bars: return []
    bars.sort(key=lambda x: -x["pct"])
    return [{
        "id": "__contact__", "title": "Capacidad de contacto",
        "subtitle": "% de registros con campo completado",
        "type": "completeness", "bars": bars,
    }]


def build_programs_section(fields, field_values, total):
    bars = []
    seen_labels = set()
    for f in fields:
        vals = field_values[f.name]
        count = sum(
            1 for v in vals
            if v is not None and str(v).strip() and norm(v) not in ("no", "0", "0.0", "")
        )
        if count == 0: continue
        label = f.label.strip()
        year_match = re.search(r'(20\d{2})', f.name)
        if label in seen_labels:
            label = f"{label} ({year_match.group(1)})" if year_match else f"{label} (2)"
        seen_labels.add(label)
        bars.append({
            "label": label[:40], "value": count,
            "pct": round(count / total * 100, 1),
            "color": COLORS[len(bars) % len(COLORS)]
        })
    if not bars: return []
    bars.sort(key=lambda x: -x["value"])
    return [{
        "id": "__programs__", "title": "Participación en programas institucionales",
        "subtitle": f"{len(bars)} programas registrados",
        "type": "bar", "bars": bars,
    }]


def build_animals_section(fields, field_values, total):
    sections = []
    animal_fields = [f for f in fields if any(k in norm(f.name) for k in ANIMAL_KW)]
    for f in animal_fields:
        vals = field_values[f.name]
        if f.type == "number":
            bins = numeric_bins(vals)
            stats = numeric_stats(vals)
            if bins and stats:
                count_with = sum(1 for v in vals if v is not None and str(v).strip() not in ("", "0"))
                sections.append({
                    "id": f.name, "title": f.label.strip(),
                    "subtitle": f"{count_with} registros · Total: {int(stats['total'])}",
                    "type": "histogram", "bars": bins, "stats": stats,
                })
        else:
            s = bar_section(f, vals, total, "Animales atendidos")
            if s: sections.append(s)
    return sections


def build_derived_kpis(classified, fields, field_values, total, existing_kpis):
    extras = []
    slots = 7 - len(existing_kpis)
    if slots <= 0:
        return extras

    contact_fields = [
        f for f in fields
        if any(k in norm(f.name) for k in {"telefono", "correo", "email", "celular", "whatsapp"})
    ]
    if contact_fields:
        con_algun = sum(
            1 for i in range(total)
            if any(field_values[f.name][i] and str(field_values[f.name][i]).strip()
                   for f in contact_fields)
        )
        pct = round(con_algun / total * 100) if total else 0
        extras.append({
            "label": "Contactables", "value": f"{pct}%",
            "sub": f"{con_algun} de {total}", "icon": "check",
        })

        if len(contact_fields) >= 2 and len(extras) < slots:
            con_multiples = sum(
                1 for i in range(total)
                if sum(1 for f in contact_fields
                       if field_values[f.name][i] and str(field_values[f.name][i]).strip()) >= 2
            )
            pct_m = round(con_multiples / total * 100) if total else 0
            extras.append({
                "label": "Contacto múltiple", "value": f"{pct_m}%",
                "sub": "2+ medios registrados", "icon": "check",
            })

    if len(extras) < slots and classified.get("location"):
        loc = classified["location"][0]
        grouped = group_similar(field_values[loc.name], top_n=1)
        if grouped:
            label, count = grouped[0]
            pct = round(count / total * 100)
            extras.append({
                "label": f"Top {loc.label.strip().lower()}",
                "value": label[:18], "sub": f"{pct}% del total", "icon": "map",
            })

    non_id_fields = [f for f in fields if f not in classified.get("identifier", [])]
    if non_id_fields and len(extras) < slots:
        fill = _global_fill_rate(non_id_fields, field_values, total)
        extras.append({
            "label": "Datos completos", "value": f"{fill}%",
            "sub": "promedio de celdas", "icon": "number",
        })

    return extras[:slots]


def build_concentration_donut(classified, field_values, total):
    if not classified.get("location"):
        return None
    loc = classified["location"][0]
    grouped = group_similar(field_values[loc.name], top_n=100)
    if len(grouped) < 4:
        return None
    top5 = grouped[:5]
    resto = sum(c for _, c in grouped[5:])
    accounted = sum(c for _, c in top5) + resto
    if accounted == 0:
        return None
    segments = [
        {"label": label, "value": count,
         "pct": round(count / accounted * 100, 1), "color": COLORS[i % len(COLORS)]}
        for i, (label, count) in enumerate(top5)
    ]
    if resto > 0:
        segments.append({"label": "Otros", "value": resto,
                          "pct": round(resto / accounted * 100, 1), "color": "#E2E8F0"})
    return {
        "id": "__concentration__",
        "title": f"Concentración por {loc.label.strip().lower()}",
        "subtitle": f"Top 5 vs resto · {len(grouped)} valores únicos",
        "type": "donut", "segments": segments,
    }


def build_contact_breakdown(fields, field_values, total):
    contact_fields = [
        f for f in fields
        if any(k in norm(f.name) for k in {"telefono", "correo", "email", "celular", "whatsapp"})
    ]
    if len(contact_fields) < 2:
        return None
    n_total_fields = len(contact_fields)
    buckets = {"todos": 0, "parcial": 0, "uno": 0, "ninguno": 0}
    for i in range(total):
        n = sum(1 for f in contact_fields
                if field_values[f.name][i] and str(field_values[f.name][i]).strip())
        if n == 0:             buckets["ninguno"] += 1
        elif n == 1:           buckets["uno"] += 1
        elif n == n_total_fields: buckets["todos"] += 1
        else:                  buckets["parcial"] += 1
    labels = [
        ("todos",   "Todos los medios", "#059669"),
        ("parcial", "Parcialmente",     "#2563EB"),
        ("uno",     "Un solo medio",    "#D97706"),
        ("ninguno", "Sin contacto",     "#DC2626"),
    ]
    bars = [
        {"label": label, "value": buckets[key],
         "pct": round(buckets[key] / total * 100, 1), "color": color}
        for key, label, color in labels if buckets[key] > 0
    ]
    if len(bars) < 2:
        return None
    return {
        "id": "__contact_breakdown__",
        "title": "Distribución de contactabilidad",
        "subtitle": f"Cruce de {n_total_fields} medios de contacto",
        "type": "bar", "bars": bars,
    }


def build_data_health(fields, field_values, total, classified):
    non_id = [f for f in fields if f not in classified.get("identifier", [])]
    if not non_id or not total:
        return None
    global_fr = _global_fill_rate(non_id, field_values, total)
    if global_fr >= 95:
        return None
    bars = sorted([
        {"label": f.label.strip(), "value": round(fill_rate(field_values[f.name], total)),
         "pct": fill_rate(field_values[f.name], total),
         "color": COLORS[0] if fill_rate(field_values[f.name], total) >= 80
                  else COLORS[5] if fill_rate(field_values[f.name], total) >= 50
                  else COLORS[6]}
        for f in non_id
    ], key=lambda x: -x["pct"])
    return {
        "id": "__data_health__",
        "title": "Calidad de datos",
        "subtitle": f"Fill rate global: {global_fr}% · {len(bars)} campos",
        "type": "completeness", "bars": bars,
    }


# ─── Orquestador genérico ─────────────────────────────────────────────────────

def build_generico(fields, field_values, total):
    classified = classify_fields(fields, field_values, total)

    contact_fields = [
        f for f in fields
        if any(k in norm(f.name) for k in {"telefono", "correo", "email", "direccion", "celular"})
    ]

    kpis = build_kpis(classified, fields, field_values, total)
    sections = []

    for f in classified["location"][:2]:
        s = bar_section(f, field_values[f.name], total, "Cobertura territorial")
        if s: sections.append(s)

    edad_fields = [f for f in classified["demographic"]
                   if "edad" in norm(f.name) or f.type == "number"]
    for f in edad_fields:
        s = build_edad_histogram(f, field_values, total)
        if s: sections.append(s)

    gender = build_gender_donut(fields, field_values, total)
    if gender: sections.append(gender)

    zona = build_zona_donut(fields, field_values, total)
    if zona: sections.append(zona)

    guias = build_guias_section(fields, field_values, total)
    if guias: sections.append(guias)

    grupos = build_grupos_section(fields, field_values, total)
    if grupos: sections.append(grupos)

    sections += build_animals_section(fields, field_values, total)

    for f in classified["yesno"]:
        if norm(f.name) in SKIP_YESNO: continue
        if any(k in norm(f.name) for k in GUIA_KEYWORDS): continue
        vals = field_values[f.name]
        yes = sum(1 for v in vals if is_yes(v))
        no  = sum(1 for v in vals if is_no(v))
        if yes + no < 5: continue
        sections.append({
            "id": f.name, "title": f.label.strip(),
            "subtitle": f"{yes} de {total} responden Sí",
            "type": "bar",
            "bars": [
                {"label": "Sí", "value": yes, "pct": round(yes / total * 100, 1), "color": COLORS[0]},
                {"label": "No", "value": no,  "pct": round(no  / total * 100, 1), "color": COLORS[6]},
            ]
        })

    sections += build_programs_section(classified["program"], field_values, total)
    sections += build_contact_section(contact_fields, field_values, total)

    for f in classified["categorical"][:3]:
        if norm(f.name) in SKIP_YESNO: continue
        if any(k in norm(f.name) for k in GUIA_KEYWORDS): continue
        s = bar_section(f, field_values[f.name], total)
        if s: sections.append(s)

    kpis += build_derived_kpis(classified, fields, field_values, total, kpis)

    conc = build_concentration_donut(classified, field_values, total)
    if conc: sections.append(conc)

    cb = build_contact_breakdown(fields, field_values, total)
    if cb: sections.append(cb)

    dh = build_data_health(fields, field_values, total, classified)
    if dh: sections.append(dh)

    return {"total": total, "kpis": kpis, "sections": sections}