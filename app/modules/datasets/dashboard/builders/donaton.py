"""
Dashboard de Donatón (recogida de alimento para perros y gatos).

Estructura del dataset:
- NOMBRE (donante)
- MUNICIPIO
- TÉLEFONO
- FECHA (string tipo "22 julio de 2025")
- ALIMENTO PERRO (kg)
- ALIMENTO GATO (kg)
- TOTAL (kg)

Devuelve KPIs y secciones renderizadas por el frontend `donaton-view`.
El cálculo se hace tolerando filas vacías y registros sin nombre
(donaciones anónimas) o sin teléfono.
"""

from collections import defaultdict
from ..formatters import COLORS, norm


_MES_KEYWORDS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}


def _safe_float(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def _find(fields, must_all=(), must_any=()):
    for f in fields:
        n = norm(f.name)
        if all(k in n for k in must_all) and (not must_any or any(k in n for k in must_any)):
            return f.name
    return None


def _parse_fecha(v) -> tuple[int | None, int | None]:
    """Devuelve (mes_num, año) tolerando 'dd <mes> de YYYY' o YYYY-MM-DD."""
    if not v:
        return None, None
    s = str(v).strip().lower()
    # Formato ISO 'YYYY-MM-DD' (raro aquí pero por si acaso)
    if len(s) >= 7 and s[:4].isdigit() and s[4] == "-":
        try:
            return int(s[5:7]), int(s[:4])
        except ValueError:
            pass
    # Formato '22 julio de 2025'
    parts = s.replace(" de ", " ").split()
    mes = año = None
    for p in parts:
        if p in _MES_KEYWORDS and mes is None:
            mes = _MES_KEYWORDS[p]
        elif p.isdigit() and len(p) == 4:
            año = int(p)
    return mes, año


def build_donaton(fields, field_values, total):
    f_mun     = _find(fields, must_any=("municipio",))
    f_perro   = _find(fields, must_all=("alimento", "perro"))
    f_gato    = _find(fields, must_all=("alimento", "gato"))
    f_total   = _find(fields, must_any=("total",))
    f_nombre  = _find(fields, must_any=("nombre",))
    f_fecha   = _find(fields, must_any=("fecha",))
    f_tel     = _find(fields, must_any=("telefono", "telé", "tele"))

    def col(name):
        return field_values.get(name, []) if name else []

    perros_vals = [_safe_float(v) for v in col(f_perro)]
    gatos_vals  = [_safe_float(v) for v in col(f_gato)]
    total_vals  = [_safe_float(v) for v in col(f_total)]
    municipios  = [str(v).strip() if v else "" for v in col(f_mun)]
    nombres     = [str(v).strip() if v else "" for v in col(f_nombre)]
    fechas      = col(f_fecha)
    telefonos   = col(f_tel)

    n_records = total

    # Si hay TOTAL precalculado lo usamos; si no, sumamos perro+gato.
    def row_total(i: int) -> float:
        t = total_vals[i] if i < len(total_vals) else None
        if t is not None:
            return t
        return (perros_vals[i] or 0) + (gatos_vals[i] or 0)

    kg_total  = sum(row_total(i) for i in range(n_records))
    kg_perro  = sum(v or 0 for v in perros_vals)
    kg_gato   = sum(v or 0 for v in gatos_vals)
    n_donantes_unicos = len({norm(n) for n in nombres if n})
    municipios_unicos = len({norm(m) for m in municipios if m})

    promedio = round(kg_total / n_records, 1) if n_records else 0

    kpis = [
        {"label": "Kg recogidos",   "value": f"{int(kg_total):,}",
         "sub": f"calculado sobre {n_records:,} donaciones",  "icon": "package"},
        {"label": "Kg para perros", "value": f"{int(kg_perro):,}",
         "sub": f"{round(kg_perro / kg_total * 100, 1) if kg_total else 0}% del total",
         "icon": "heart"},
        {"label": "Kg para gatos",  "value": f"{int(kg_gato):,}",
         "sub": f"{round(kg_gato / kg_total * 100, 1) if kg_total else 0}% del total",
         "icon": "heart"},
        {"label": "Donantes únicos", "value": f"{n_donantes_unicos:,}",
         "sub": f"en {municipios_unicos} municipios", "icon": "users"},
    ]

    sections = []

    # ── Top municipios por kg ──────────────────────────────────────────
    by_mun: dict[str, float] = defaultdict(float)
    for i, m in enumerate(municipios):
        if not m:
            continue
        by_mun[m] += row_total(i)
    if by_mun:
        ordered = sorted(by_mun.items(), key=lambda kv: -kv[1])[:12]
        ref = ordered[0][1] or 1
        sections.append({
            "id": "__don_mun__",
            "title": "Top municipios por kg recogidos",
            "subtitle": f"{len(by_mun)} municipios · {int(kg_total):,} kg totales",
            "type": "bar", "span": "full",
            "bars": [
                {"label": label, "value": round(v),
                 "pct": round(v / ref * 100, 1),
                 "color": COLORS[i % len(COLORS)]}
                for i, (label, v) in enumerate(ordered)
            ],
        })

    # ── Composición perro vs gato (donut) ─────────────────────────────
    suma_pg = (kg_perro + kg_gato) or 1
    sections.append({
        "id": "__don_composicion__",
        "title": "Distribución del alimento",
        "subtitle": "Perros vs Gatos",
        "type": "donut", "span": "half",
        "segments": [
            {"label": "Perros", "value": round(kg_perro),
             "pct": round(kg_perro / suma_pg * 100, 1), "color": "#2563EB"},
            {"label": "Gatos",  "value": round(kg_gato),
             "pct": round(kg_gato / suma_pg * 100, 1), "color": "#DB2777"},
        ],
    })

    # ── Top donantes por kg (bar horizontal) ──────────────────────────
    by_donante: dict[str, float] = defaultdict(float)
    for i, n in enumerate(nombres):
        if not n:
            continue
        by_donante[n] += row_total(i)
    if by_donante:
        ordered = sorted(by_donante.items(), key=lambda kv: -kv[1])[:10]
        ref = ordered[0][1] or 1
        sections.append({
            "id": "__don_donantes__",
            "title": "Top donantes",
            "subtitle": f"{n_donantes_unicos} donantes registrados",
            "type": "bar", "span": "half",
            "bars": [
                {"label": label, "value": round(v),
                 "pct": round(v / ref * 100, 1),
                 "color": COLORS[i % len(COLORS)]}
                for i, (label, v) in enumerate(ordered)
            ],
        })

    # ── Recogida por mes (bar) ────────────────────────────────────────
    by_mes: dict[tuple[int, int], float] = defaultdict(float)
    for i, f in enumerate(fechas):
        mes, año = _parse_fecha(f)
        if mes is None or año is None:
            continue
        by_mes[(año, mes)] += row_total(i)
    if by_mes:
        meses_es = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        ordered = sorted(by_mes.items())
        ref = max(v for _, v in ordered) or 1
        sections.append({
            "id": "__don_mes__",
            "title": "Recogida por mes",
            "subtitle": "Kg agrupados por mes",
            "type": "bar", "span": "full",
            "bars": [
                {"label": f"{meses_es[m - 1]} {y}",
                 "value": round(v),
                 "pct": round(v / ref * 100, 1),
                 "color": COLORS[i % len(COLORS)]}
                for i, ((y, m), v) in enumerate(ordered)
            ],
        })

    # ── Completitud (datos opcionales) ────────────────────────────────
    n_con_nombre = sum(1 for n in nombres if n)
    n_con_tel    = sum(1 for t in telefonos if t)
    if n_records:
        sections.append({
            "id": "__don_completeness__",
            "title": "Completitud de los registros",
            "subtitle": f"% del total de {n_records:,} donaciones",
            "type": "completeness", "span": "full",
            "bars": [
                {"label": "Con nombre del donante",
                 "value": round(n_con_nombre / n_records * 100, 1),
                 "pct":   round(n_con_nombre / n_records * 100, 1),
                 "color": COLORS[0]},
                {"label": "Con teléfono",
                 "value": round(n_con_tel / n_records * 100, 1),
                 "pct":   round(n_con_tel / n_records * 100, 1),
                 "color": COLORS[1]},
            ],
        })

    return {
        "total": n_records,
        "kpis": kpis,
        "sections": sections,
        "project_label": (
            f"{int(kg_total):,} kg recogidos en {municipios_unicos} municipios "
            f"· KPIs calculados a partir de {n_records:,} registros"
        ),
    }
