from ..formatters import COLORS, norm, numeric_bins, numeric_stats


def build_censo_animal(fields, field_values, total):

    def _safe_float(v):
        try: return float(v)
        except: return None

    def col(name):
        return field_values.get(name, [])

    def _find(must_all=(), must_any=()):
        for f in fields:
            n = norm(f.name)
            if all(k in n for k in must_all) and (not must_any or any(k in n for k in must_any)):
                return f.name
        return None

    f_mun          = _find(must_any=("municipio",))
    f_perros_pob   = _find(must_all=("poblacion", "perros"))
    f_gatos_pob    = _find(must_all=("poblacion", "gatos"))
    f_vta          = _find(must_any=("vta",))
    f_viviendas    = _find(must_any=("viviendas",))
    f_perros_rep   = _find(must_all=("perros", "reportados"))
    f_gatos_rep    = _find(must_all=("gatos", "reportados"))
    f_ratio_perros = _find(must_all=("perros", "vivienda"))
    f_ratio_gatos  = _find(must_all=("gatos", "vivienda"))

    municipios_raw = col(f_mun) if f_mun else []
    TOTALES_KW = {"valle del cauca", "valle", "total"}

    def is_total(v):
        return norm(str(v)) in TOTALES_KW if v else False

    total_idx = next((i for i, v in enumerate(municipios_raw) if is_total(v)), None)
    valid_idx = [i for i, v in enumerate(municipios_raw)
                 if v and str(v).strip() and not is_total(v)]
    n_mun = len(valid_idx)

    def kpi_val(fname):
        if not fname: return 0
        raw = col(fname)
        if total_idx is not None and total_idx < len(raw):
            v = _safe_float(raw[total_idx])
            if v is not None: return v
        return sum(_safe_float(raw[i]) or 0 for i in valid_idx if i < len(raw))

    total_perros = kpi_val(f_perros_pob)
    total_gatos  = kpi_val(f_gatos_pob)
    total_viv    = kpi_val(f_viviendas)
    total_vta    = kpi_val(f_vta)
    mun_enc = sum(1 for i in valid_idx
                  if f_viviendas and i < len(col(f_viviendas))
                  and _safe_float(col(f_viviendas)[i]))

    kpis = [
        {"label": "Población perros Valle", "value": f"{int(total_perros):,}", "sub": "estimado 2026",           "icon": "number"},
        {"label": "Población gatos Valle",  "value": f"{int(total_gatos):,}",  "sub": "estimado 2026",           "icon": "number"},
        {"label": "Municipios encuestados", "value": str(mun_enc),             "sub": f"de {n_mun} en el Valle", "icon": "map"},
        {"label": "Vacunaciones (VTA)",     "value": f"{int(total_vta):,}",    "sub": "total reportadas",        "icon": "check"},
    ]

    sections = []

    def bar_mun(fname, sec_id, title, subtitle, top_n=15, span="full"):
        if not fname: return None
        raw = col(fname)
        pairs = []
        for i in valid_idx:
            if i >= len(raw): continue
            v = _safe_float(raw[i])
            if not v or v <= 0: continue
            pairs.append((str(municipios_raw[i]).strip(), v))
        if not pairs: return None
        pairs.sort(key=lambda x: -x[1])
        pairs = pairs[:top_n]
        ref = sum(v for _, v in pairs) or 1
        return {
            "id": sec_id, "title": title, "subtitle": subtitle,
            "type": "bar", "span": span,
            "bars": [{"label": m, "value": round(v),
                      "pct": round(v / ref * 100, 1),
                      "color": COLORS[i % len(COLORS)]}
                     for i, (m, v) in enumerate(pairs)],
        }

    def ratio_hist(fname, sec_id, title, span="half"):
        if not fname: return None
        vals = [_safe_float(col(fname)[i]) for i in valid_idx
                if i < len(col(fname)) and _safe_float(col(fname)[i]) is not None]
        bins = numeric_bins(vals)
        stats = numeric_stats(vals)
        if not bins: return None
        return {
            "id": sec_id, "title": title,
            "subtitle": f"Promedio: {stats.get('avg', 0)} · {len(vals)} municipios",
            "type": "histogram", "span": span, "bars": bins,
        }

    # FILA 1 (full)
    s = bar_mun(f_perros_pob, "__perros_mun__",
                "Población de perros por municipio",
                f"Top 15 · estimado 2026 · total {int(total_perros):,}", span="full")
    if s: sections.append(s)

    # FILA 2 (full)
    s = bar_mun(f_gatos_pob, "__gatos_mun__",
                "Población de gatos por municipio",
                f"Top 15 · estimado 2026 · total {int(total_gatos):,}", span="full")
    if s: sections.append(s)

    # FILA 3: Viviendas (half) + Ratio perros (half)
    s = bar_mun(f_viviendas, "__viv_mun__",
                "Viviendas encuestadas por municipio",
                f"Cobertura del censo · total {int(total_viv):,}",
                top_n=12, span="half")
    if s: sections.append(s)

    s = ratio_hist(f_ratio_perros, "__ratio_perros__",
                   "Densidad perros / vivienda", span="half")
    if s: sections.append(s)

    # FILA 4: Ratio gatos (half) + Donut (half)
    s = ratio_hist(f_ratio_gatos, "__ratio_gatos__",
                   "Densidad gatos / vivienda", span="half")
    if s: sections.append(s)

    total_animal = total_perros + total_gatos or 1
    sections.append({
        "id": "__composicion__",
        "title": "Composición animal",
        "subtitle": f"Perros vs Gatos · {int(total_animal):,} animales estimados",
        "type": "donut", "span": "half",
        "segments": [
            {"label": "Perros", "value": round(total_perros),
             "pct": round(total_perros / total_animal * 100, 1), "color": "#2563EB"},
            {"label": "Gatos",  "value": round(total_gatos),
             "pct": round(total_gatos  / total_animal * 100, 1), "color": "#DB2777"},
        ]
    })

    # FILA 5 (full)
    s = bar_mun(f_vta, "__vta_mun__",
                "Vacunaciones (VTA) por municipio",
                "Solo municipios con VTA registrada", span="full")
    if s: sections.append(s)

    # FILA 6 (full): Completeness
    comp_bars = []
    for fname, label in [(f_viviendas,  "Viviendas encuestadas"),
                          (f_perros_rep, "Perros reportados"),
                          (f_gatos_rep,  "Gatos reportados"),
                          (f_vta,        "VTA registradas")]:
        if not fname: continue
        n_filled = sum(1 for i in valid_idx
                       if i < len(col(fname)) and _safe_float(col(fname)[i]) is not None)
        pct = round(n_filled / n_mun * 100, 1) if n_mun else 0
        comp_bars.append({
            "label": label, "value": pct, "pct": pct,
            "color": COLORS[0] if pct >= 80 else COLORS[5] if pct >= 50 else COLORS[6],
        })
    if comp_bars:
        sections.append({
            "id": "__censo_completeness__",
            "title": "Cobertura de encuesta por campo",
            "subtitle": f"% de municipios con dato · {n_mun} municipios",
            "type": "completeness", "span": "full", "bars": comp_bars,
        })

    return {"total": n_mun, "kpis": kpis, "sections": sections}