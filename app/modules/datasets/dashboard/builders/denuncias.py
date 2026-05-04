"""
Dashboard de Denuncias (reportes de presunto maltrato animal).

Estructura del dataset:
- Fecha (timestamp del registro)
- Número de caso
- Fecha del presunto maltrato
- Nombre del denunciante
- Tipo y número de documento
- Denuncia anónima
- Ubicación (zona, barrio/vereda, dirección, anotaciones)
- Cantidad de animales por especie
- Descripción de los hechos
- Petición a la entidad
- Datos de contacto (correo, celular, whatsapp, otro)
- Adjuntos (fotos/videos)
- Municipio
- Especie afectada
- Datos del cuidador
- Horario de ubicación
- Autorización
- Motivo de la denuncia (Maltrato animal / Convivencia / Mala tenencia / Abandono)
- Seguimientos (gestión 1 y 2)

Devuelve KPIs y secciones renderizadas por el frontend `denuncias-view`.
"""

from collections import defaultdict
from datetime import datetime
from ..formatters import COLORS, norm, _group_key, group_similar


_MES_KEYWORDS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# Categorías canónicas del campo "Motivo de la Denuncia" (texto largo)
MOTIVOS = [
    ("Maltrato animal",         "maltrato"),
    ("Problema de convivencia", "convivencia"),
    ("Mala tenencia",           "mala tenencia"),
    ("Abandono",                "abandono"),
]


def _find_field(fields, must_all=(), must_any=(), forbid=()):
    """Devuelve el `name` del primer field que cumpla los criterios."""
    for f in fields:
        n = norm(f.name)
        if any(k in n for k in forbid):
            continue
        if must_all and not all(k in n for k in must_all):
            continue
        if must_any and not any(k in n for k in must_any):
            continue
        return f.name
    return None


def _parse_fecha(v) -> tuple[int | None, int | None]:
    """Devuelve (mes_num, año) tolerando ISO, Timestamp.isoformat o '22 julio de 2025'."""
    if v is None:
        return None, None
    if isinstance(v, datetime):
        return v.month, v.year
    s = str(v).strip().lower()
    if not s:
        return None, None
    # ISO 'YYYY-MM-DD...' (lo más común tras normalize_value)
    if len(s) >= 7 and s[:4].isdigit() and s[4] == "-":
        try:
            return int(s[5:7]), int(s[:4])
        except ValueError:
            pass
    parts = s.replace(" de ", " ").split()
    mes = año = None
    for p in parts:
        if p in _MES_KEYWORDS and mes is None:
            mes = _MES_KEYWORDS[p]
        elif p.isdigit() and len(p) == 4:
            año = int(p)
    return mes, año


def _classify_motivo(value: str) -> str | None:
    if not value:
        return None
    v = _group_key(value)
    for label, key in MOTIVOS:
        if key in v:
            return label
    return None


def _is_anonima(value) -> bool:
    if value is None:
        return False
    v = _group_key(value)
    return v in ("si", "sí", "yes", "1", "true", "anonima", "anonimo")


def build_denuncias(fields, field_values, total):
    f_fecha     = _find_field(fields, must_any=("fecha",), forbid=("presunto", "diligenciamiento"))
    f_fecha_alt = _find_field(fields, must_any=("fecha",))
    f_municipio = _find_field(fields, must_all=("municipio",))
    f_especie   = _find_field(fields, must_all=("especie",))
    f_motivo    = _find_field(fields, must_all=("motivo",))
    f_anon      = _find_field(fields, must_all=("anonima",)) or \
                  _find_field(fields, must_all=("anonim",))
    f_zona      = _find_field(fields, must_all=("zona",))
    f_correo    = _find_field(fields, must_any=("correo", "email"))
    f_celular   = _find_field(fields, must_any=("celular",))
    f_whatsapp  = _find_field(fields, must_any=("whatsapp",))
    f_otro_tel  = _find_field(fields, must_all=("otro",), must_any=("contacto", "telefono", "numero"))
    f_adjuntos  = _find_field(fields, must_any=("adjunta", "fotos", "videos"))
    f_gestion1  = _find_field(fields, must_all=("gestion",), must_any=("1",)) or \
                  _find_field(fields, must_all=("seguimiento",), must_any=("1",))
    f_gestion2  = _find_field(fields, must_all=("gestion",), must_any=("2",)) or \
                  _find_field(fields, must_all=("seguimiento",), must_any=("2",))

    f_fecha_kpi = f_fecha or f_fecha_alt

    def col(name):
        return field_values.get(name, []) if name else []

    municipios = [str(v).strip() if v else "" for v in col(f_municipio)]
    especies   = [str(v).strip() if v else "" for v in col(f_especie)]
    motivos    = [_classify_motivo(v) for v in col(f_motivo)]
    anonimas   = [_is_anonima(v) for v in col(f_anon)]
    zonas      = [str(v).strip() if v else "" for v in col(f_zona)]
    fechas     = col(f_fecha_kpi)
    correos    = col(f_correo)
    celulares  = col(f_celular)
    whatsapps  = col(f_whatsapp)
    otros_tel  = col(f_otro_tel)
    adjuntos   = col(f_adjuntos)
    gestion1   = col(f_gestion1)
    gestion2   = col(f_gestion2)

    n = total

    # ── KPIs ──────────────────────────────────────────────────────────
    n_municipios = len({_group_key(m) for m in municipios if m})
    n_anonimas   = sum(1 for a in anonimas if a)
    n_con_motivo = sum(1 for m in motivos if m)
    n_con_correo = sum(1 for c in correos if c and str(c).strip())
    n_con_tel    = sum(1 for i in range(n)
                       if (i < len(celulares) and celulares[i] and str(celulares[i]).strip())
                       or (i < len(whatsapps) and whatsapps[i] and str(whatsapps[i]).strip())
                       or (i < len(otros_tel) and otros_tel[i] and str(otros_tel[i]).strip()))
    n_con_adjuntos = sum(1 for v in adjuntos if v and str(v).strip())
    n_gestionadas = sum(1 for i in range(n)
                        if (i < len(gestion1) and gestion1[i] and str(gestion1[i]).strip())
                        or (i < len(gestion2) and gestion2[i] and str(gestion2[i]).strip()))

    pct = lambda x, base: round(x / base * 100, 1) if base else 0

    kpis = [
        {"label": "Denuncias recibidas", "value": f"{n:,}",
         "sub": f"en {n_municipios} municipios",      "icon": "clipboard"},
        {"label": "Anónimas",            "value": f"{n_anonimas:,}",
         "sub": f"{pct(n_anonimas, n)}% del total",   "icon": "shield"},
        {"label": "Con seguimiento",     "value": f"{n_gestionadas:,}",
         "sub": f"{pct(n_gestionadas, n)}% gestionadas", "icon": "check"},
        {"label": "Con evidencia",       "value": f"{n_con_adjuntos:,}",
         "sub": f"{pct(n_con_adjuntos, n)}% con adjuntos", "icon": "paperclip"},
        {"label": "Contactables",        "value": f"{pct(n_con_tel + n_con_correo if False else max(n_con_tel, n_con_correo), n)}%",
         "sub": f"{n_con_tel} con tel · {n_con_correo} con correo", "icon": "phone"},
    ]

    sections = []

    # ── Motivos de la denuncia (donut) ────────────────────────────────
    by_motivo: dict[str, int] = defaultdict(int)
    for m in motivos:
        if m:
            by_motivo[m] += 1
    if by_motivo:
        accounted = sum(by_motivo.values())
        palette = {"Maltrato animal": "#DC2626", "Problema de convivencia": "#D97706",
                   "Mala tenencia": "#7C3AED", "Abandono": "#0891B2"}
        segments = [
            {"label": label, "value": by_motivo[label],
             "pct": round(by_motivo[label] / accounted * 100, 1),
             "color": palette.get(label, "#64748B")}
            for label, _ in MOTIVOS if by_motivo.get(label)
        ]
        sin_clasif = n - accounted
        if sin_clasif > 0:
            segments.append({"label": "Sin clasificar", "value": sin_clasif,
                             "pct": round(sin_clasif / n * 100, 1), "color": "#E2E8F0"})
        sections.append({
            "id": "__den_motivo__",
            "title": "Motivo de la denuncia",
            "subtitle": f"{accounted} de {n} clasificadas",
            "type": "donut", "span": "half", "segments": segments,
        })

    # ── Especies afectadas (bar) ──────────────────────────────────────
    grouped_esp = group_similar(especies, top_n=10)
    if grouped_esp:
        ref = grouped_esp[0][1] or 1
        sections.append({
            "id": "__den_especie__",
            "title": "Especies afectadas",
            "subtitle": f"{len(grouped_esp)} especies registradas",
            "type": "bar", "span": "half",
            "bars": [
                {"label": label, "value": count,
                 "pct": round(count / ref * 100, 1),
                 "color": COLORS[i % len(COLORS)]}
                for i, (label, count) in enumerate(grouped_esp)
            ],
        })

    # ── Top municipios por denuncias ──────────────────────────────────
    by_mun: dict[str, int] = defaultdict(int)
    by_mun_label: dict[str, str] = {}
    for m in municipios:
        if not m:
            continue
        k = _group_key(m)
        by_mun[k] += 1
        by_mun_label.setdefault(k, m)
    if by_mun:
        ordered = sorted(by_mun.items(), key=lambda kv: -kv[1])[:12]
        ref = ordered[0][1] or 1
        sections.append({
            "id": "__den_municipio__",
            "title": "Top municipios por denuncias",
            "subtitle": f"{len(by_mun)} municipios · {n:,} denuncias",
            "type": "bar", "span": "full",
            "bars": [
                {"label": by_mun_label[k], "value": v,
                 "pct": round(v / ref * 100, 1),
                 "color": COLORS[i % len(COLORS)]}
                for i, (k, v) in enumerate(ordered)
            ],
        })

    # ── Denuncias por mes ─────────────────────────────────────────────
    by_mes: dict[tuple[int, int], int] = defaultdict(int)
    for f in fechas:
        mes, año = _parse_fecha(f)
        if mes is None or año is None:
            continue
        by_mes[(año, mes)] += 1
    if by_mes:
        meses_es = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        ordered = sorted(by_mes.items())
        ref = max(v for _, v in ordered) or 1
        sections.append({
            "id": "__den_mes__",
            "title": "Denuncias por mes",
            "subtitle": "Volumen mensual de reportes",
            "type": "bar", "span": "full",
            "bars": [
                {"label": f"{meses_es[m - 1]} {y}",
                 "value": v, "pct": round(v / ref * 100, 1),
                 "color": COLORS[i % len(COLORS)]}
                for i, ((y, m), v) in enumerate(ordered)
            ],
        })

    # ── Anónimas vs identificadas ─────────────────────────────────────
    if any(anonimas):
        ident = n - n_anonimas
        sections.append({
            "id": "__den_anonimato__",
            "title": "Identificación del denunciante",
            "subtitle": f"{n:,} denuncias",
            "type": "donut", "span": "half",
            "segments": [
                {"label": "Anónima",      "value": n_anonimas,
                 "pct": round(n_anonimas / n * 100, 1), "color": "#64748B"},
                {"label": "Identificada", "value": ident,
                 "pct": round(ident / n * 100, 1), "color": "#2563EB"},
            ],
        })

    # ── Zona del municipio (rural/urbana, donut) ──────────────────────
    grouped_zona = group_similar(zonas, top_n=6)
    if grouped_zona:
        accounted = sum(c for _, c in grouped_zona)
        sections.append({
            "id": "__den_zona__",
            "title": "Zona del municipio",
            "subtitle": f"{accounted} de {n} con zona registrada",
            "type": "donut", "span": "half",
            "segments": [
                {"label": label, "value": count,
                 "pct": round(count / accounted * 100, 1),
                 "color": COLORS[i % len(COLORS)]}
                for i, (label, count) in enumerate(grouped_zona)
            ],
        })

    # ── Completitud / capacidad de seguimiento ────────────────────────
    if n:
        sections.append({
            "id": "__den_completitud__",
            "title": "Completitud y capacidad de seguimiento",
            "subtitle": f"% del total de {n:,} denuncias",
            "type": "completeness", "span": "full",
            "bars": [
                {"label": "Con correo del denunciante",
                 "value": pct(n_con_correo, n), "pct": pct(n_con_correo, n), "color": COLORS[0]},
                {"label": "Con teléfono o WhatsApp",
                 "value": pct(n_con_tel, n),    "pct": pct(n_con_tel, n),    "color": COLORS[1]},
                {"label": "Con adjuntos (fotos/videos)",
                 "value": pct(n_con_adjuntos, n), "pct": pct(n_con_adjuntos, n), "color": COLORS[2]},
                {"label": "Con motivo clasificado",
                 "value": pct(n_con_motivo, n), "pct": pct(n_con_motivo, n), "color": COLORS[3]},
                {"label": "Con seguimiento (gestión 1 ó 2)",
                 "value": pct(n_gestionadas, n), "pct": pct(n_gestionadas, n), "color": COLORS[5]},
            ],
        })

    return {
        "total": n,
        "kpis": kpis,
        "sections": sections,
        "project_label": (
            f"{n:,} denuncias en {n_municipios} municipios · "
            f"{n_anonimas:,} anónimas · {n_gestionadas:,} con seguimiento"
        ),
    }
