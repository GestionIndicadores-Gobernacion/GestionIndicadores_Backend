import re
from .formatters import (
    COLORS, norm, is_yes, is_no, fill_rate,
    group_similar, make_bars, bar_section,
    numeric_bins, numeric_stats, unique_clean
)

# ─── Constantes de dominio ────────────────────────────────────────────────────

GENDER_FIELDS  = {"mujer", "hombre", "intersesual", "lgbtiq_"}
ZONA_FIELDS    = {"rural", "urbana"}
GUIA_KEYWORDS  = {"guia", "guía"}
GRUPOS_FIELDS  = {"afro", "indigena", "rrom", "discapacidad", "victima", "reincorporado"}
SKIP_YESNO     = GENDER_FIELDS | ZONA_FIELDS | GRUPOS_FIELDS
ANIMAL_KW      = {"perro", "gato", "animal", "especie", "felino", "canino"}


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


# ─── Secciones especiales ─────────────────────────────────────────────────────

def build_gender_donut(fields, field_values, total):
    labels = {
        "mujer":      ("Mujer",       "#DB2777"),
        "hombre":     ("Hombre",      "#2563EB"),
        "intersesual": ("Intersexual", "#7C3AED"),
        "lgbtiq_":    ("LGBTIQ+",     "#0891B2"),
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
        "id": "__gender__",
        "title": "Distribución por género",
        "subtitle": f"{accounted} de {total} con género registrado",
        "type": "donut",
        "segments": segments,
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
        "id": "__zona__",
        "title": "Zona de residencia",
        "subtitle": f"Rural vs Urbana · {total} registros",
        "type": "donut",
        "segments": segments,
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
        bars.append({
            "label": f.label.strip(),
            "value": count,
            "pct": round(count / total * 100, 1),
            "color": colors[i % len(colors)],
        })

    if not bars: return None

    return {
        "id": "__guias__",
        "title": "Participación por guía",
        "subtitle": f"{len(bars)} guías registradas",
        "type": "bar",
        "bars": bars,
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
        "id": "__grupos__",
        "title": "Grupos diferenciales",
        "subtitle": "Población con enfoque diferencial",
        "type": "bar",
        "bars": bars,
    }


def build_edad_histogram(field, field_values, total):
    vals = field_values[field.name]
    bins = numeric_bins(vals)
    stats = numeric_stats(vals)
    if not bins: return None
    return {
        "id": field.name,
        "title": field.label.strip(),
        "subtitle": f"Distribución por rangos · Promedio: {stats.get('avg', 0)} años",
        "type": "histogram",
        "bars": bins,
    }


def build_contact_section(fields, field_values, total):
    bars = []
    for f in fields:
        rate = fill_rate(field_values[f.name], total)
        bars.append({
            "label": f.label.strip(),
            "value": round(rate),
            "pct": rate,
            "color": COLORS[0] if rate >= 80 else COLORS[2] if rate >= 50 else COLORS[6]
        })
    if not bars: return []
    bars.sort(key=lambda x: -x["pct"])
    return [{
        "id": "__contact__",
        "title": "Capacidad de contacto",
        "subtitle": "% de registros con campo completado",
        "type": "completeness",
        "bars": bars,
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
            "label": label[:40],
            "value": count,
            "pct": round(count / total * 100, 1),
            "color": COLORS[len(bars) % len(COLORS)]
        })

    if not bars: return []
    bars.sort(key=lambda x: -x["value"])
    return [{
        "id": "__programs__",
        "title": "Participación en programas institucionales",
        "subtitle": f"{len(bars)} programas registrados",
        "type": "bar",
        "bars": bars,
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
                    "id": f.name,
                    "title": f.label.strip(),
                    "subtitle": f"{count_with} registros · Total: {int(stats['total'])}",
                    "type": "histogram",
                    "bars": bins,
                    "stats": stats,
                })
        else:
            s = bar_section(f, vals, total, "Animales atendidos")
            if s: sections.append(s)

    return sections

def build_presupuesto_kpis(field_values, total):
    def total_col(col):
        vals = field_values.get(col, [])
        return sum(float(v) for v in vals if v is not None and str(v).strip())

    apropiacion   = total_col("apropiacion_definitiva")
    cdp           = total_col("cdp_ejecutado")
    pagos         = total_col("total_pagos")
    disponible    = total_col("presup_disponible")
    pct           = round(cdp / apropiacion * 100, 1) if apropiacion else 0

    return [
        {"label": "Apropiación definitiva", "value": f"${apropiacion:,.0f}",  "sub": "presupuesto total",       "icon": "number"},
        {"label": "CDP ejecutado",           "value": f"${cdp:,.0f}",          "sub": f"{pct}% de apropiación",  "icon": "check"},
        {"label": "Total pagos",             "value": f"${pagos:,.0f}",        "sub": "pagos realizados",        "icon": "number"},
        {"label": "Presup. disponible",      "value": f"${disponible:,.0f}",   "sub": "saldo sin comprometer",   "icon": "number"},
    ]


def build_presupuesto_ejecucion_bar(field_values, total):
    """Barra comparativa: Apropiación vs CDP vs Pagos"""
    def total_col(col):
        vals = field_values.get(col, [])
        return sum(float(v) for v in vals if v is not None and str(v).strip())

    apropiacion = total_col("apropiacion_definitiva")
    cdp         = total_col("cdp_ejecutado")
    pagos       = total_col("total_pagos")
    if not apropiacion:
        return None

    return {
        "id": "__ejecucion__",
        "title": "Resumen de ejecución presupuestal",
        "subtitle": "Apropiación, CDP y Pagos en pesos",
        "type": "bar",
        "bars": [
            {"label": "Apropiación",  "value": apropiacion, "pct": 100,                              "color": "#1B3A6B"},
            {"label": "CDP",          "value": cdp,         "pct": round(cdp / apropiacion * 100, 1), "color": "#2563EB"},
            {"label": "Pagos",        "value": pagos,       "pct": round(pagos / apropiacion * 100, 1),"color": "#0891B2"},
        ]
    }


def build_presupuesto_by_grupo(fields, field_values, total):
    """Ejecución por grupo (Funcionamiento vs Inversión)"""
    grupo_field  = next((f for f in fields if f.name == "desc_grupo"), None)
    cdp_field    = "cdp_ejecutado"
    aprop_field  = "apropiacion_definitiva"
    if not grupo_field:
        return None

    grupos: dict = {}
    for i, grupo in enumerate(field_values[grupo_field.name]):
        if not grupo:
            continue
        g = str(grupo).strip()
        if g not in grupos:
            grupos[g] = {"aprop": 0, "cdp": 0}
        try: grupos[g]["aprop"] += float(field_values[aprop_field][i] or 0)
        except: pass
        try: grupos[g]["cdp"]   += float(field_values[cdp_field][i] or 0)
        except: pass

    if not grupos:
        return None

    colors = ["#1B3A6B", "#2563EB", "#0891B2", "#059669"]
    bars = []
    for i, (grupo, vals) in enumerate(grupos.items()):
        pct = round(vals["cdp"] / vals["aprop"] * 100, 1) if vals["aprop"] else 0
        bars.append({
            "label": grupo,
            "value": vals["cdp"],
            "pct": pct,
            "color": colors[i % len(colors)]
        })

    return {
        "id": "__por_grupo__",
        "title": "CDP ejecutado por grupo",
        "subtitle": "Funcionamiento vs Inversión",
        "type": "bar",
        "bars": sorted(bars, key=lambda x: -x["value"])
    }


def build_presupuesto_by_proyecto(fields, field_values, total):
    """Top proyectos por apropiación"""
    proj_field  = next((f for f in fields if f.name == "descripcion_proyecto"), None)
    aprop_field = "apropiacion_definitiva"
    if not proj_field:
        return None

    proyectos: dict = {}
    for i, proj in enumerate(field_values[proj_field.name]):
        if not proj or str(proj).strip() in ("", "nan"):
            continue
        p = str(proj).strip()[:60]
        try: proyectos[p] = proyectos.get(p, 0) + float(field_values[aprop_field][i] or 0)
        except: pass

    if not proyectos:
        return None

    colors = COLORS
    bars = sorted(proyectos.items(), key=lambda x: -x[1])[:8]
    total_aprop = sum(v for _, v in bars) or 1

    return {
        "id": "__por_proyecto__",
        "title": "Apropiación por proyecto",
        "subtitle": f"Top {len(bars)} proyectos",
        "type": "bar",
        "bars": [
            {"label": label, "value": val,
             "pct": round(val / total_aprop * 100, 1),
             "color": colors[i % len(colors)]}
            for i, (label, val) in enumerate(bars)
        ]
    }


def build_presupuesto_completeness(field_values, total):
    """% de ejecución CDP vs Apropiación por fila"""
    aprop_vals = field_values.get("apropiacion_definitiva", [])
    cdp_vals   = field_values.get("cdp_ejecutado", [])
    pago_vals  = field_values.get("total_pagos", [])

    aprop_total = sum(float(v) for v in aprop_vals if v) or 1
    cdp_total   = sum(float(v) for v in cdp_vals if v)
    pago_total  = sum(float(v) for v in pago_vals if v)

    pct_cdp   = round(cdp_total / aprop_total * 100, 1)
    pct_pagos = round(pago_total / aprop_total * 100, 1)
    pct_disp  = round(100 - pct_cdp, 1)

    return {
        "id": "__completeness_presupuesto__",
        "title": "Nivel de ejecución",
        "subtitle": "% sobre apropiación definitiva",
        "type": "completeness",
        "bars": [
            {"label": "CDP ejecutado",      "value": pct_cdp,   "pct": pct_cdp,   "color": "#2563EB"},
            {"label": "Pagos realizados",   "value": pct_pagos, "pct": pct_pagos, "color": "#0891B2"},
            {"label": "Presup. disponible", "value": pct_disp,  "pct": pct_disp,  "color": "#E2E8F0"},
        ]
    }