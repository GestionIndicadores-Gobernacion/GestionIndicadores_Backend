from ..formatters import COLORS, norm

_PROYECTO_KW = "animalista"


def _filas_proyecto(fields, field_values):
    f_proyecto = next(
        (f for f in fields if "proyecto" in norm(f.name) and "descripcion" in norm(f.name)),
        None
    )
    if not f_proyecto:
        return list(range(len(next(iter(field_values.values())))))
    vals = field_values[f_proyecto.name]
    idx = [i for i, v in enumerate(vals) if v and _PROYECTO_KW in norm(str(v))]
    return idx if idx else list(range(len(vals)))


def _safe_float(vals, i):
    if i >= len(vals) or vals[i] is None:
        return 0.0
    try:
        return float(vals[i])
    except Exception:
        return 0.0


def _col_sum(field_values, name, rows):
    if not name: return 0
    vals = field_values.get(name, [])
    total = 0
    for i in rows:
        if i >= len(vals): continue
        v = vals[i]
        if v is None: continue
        try: total += float(v)
        except: pass
    return total


def _col_avg(field_values, name, rows):
    if not name: return 0
    vals = field_values.get(name, [])
    nums = []
    for i in rows:
        if i >= len(vals): continue
        v = vals[i]
        if v is None: continue
        try: nums.append(float(v))
        except: pass
    return round(sum(nums) / len(nums), 1) if nums else 0


def _fname_exact(fields, exact_norm):
    """Busca campo cuyo nombre normalizado sea exactamente igual."""
    for f in fields:
        if norm(f.name) == exact_norm:
            return f.name
    return None


def _fname_all(fields, *keywords):
    """Busca campo cuyo nombre normalizado contenga TODAS las keywords."""
    for f in fields:
        n = norm(f.name)
        if all(k in n for k in keywords):
            return f.name
    return None


def build_presupuesto(fields, field_values, total):
    idx = _filas_proyecto(fields, field_values)

    # Nombres reales — orden de búsqueda importa
    fn_aprop = _fname_exact(fields, "apropiacion_definitiva")
    fn_cdp   = _fname_exact(fields, "cdp_ejecutado")
    fn_oblig = _fname_exact(fields, "total_obligaciones")
    fn_pagos = _fname_exact(fields, "total_pagos")
    fn_disp  = _fname_exact(fields, "presup_disponible")
    fn_ejec  = _fname_exact(fields, "ejecutado")          # '% Ejecutado' → 'ejecutado'
    fn_rubro = _fname_exact(fields, "descripcion_apropiacion_rubro")

    # Fallbacks formato antiguo
    if not fn_aprop: fn_aprop = _fname_all(fields, "apropiacion", "definitiva")
    if not fn_cdp:   fn_cdp   = _fname_all(fields, "cdp", "ejecutado")
    if not fn_oblig: fn_oblig = _fname_all(fields, "total", "obligaciones")
    if not fn_pagos: fn_pagos = _fname_all(fields, "total", "pagos")
    if not fn_disp:  fn_disp  = _fname_all(fields, "presup", "disponible")
    if not fn_rubro: fn_rubro = _fname_all(fields, "descripcion", "rubro")

    # Fallbacks nuevo formato presupuestal (C.Gestor / Fondo / Descripcion PEP)
    if not fn_cdp:   fn_cdp   = _fname_exact(fields, "total_ejecutado")
    if not fn_rubro: fn_rubro = _fname_exact(fields, "descripcion_pep")
    if not fn_rubro: fn_rubro = _fname_exact(fields, "descripcion_proyecto")

    # Etiqueta dinámica para el KPI de ejecución comprometida
    cdp_label = "Total ejecutado" if (fn_cdp and norm(fn_cdp) == "total_ejecutado") else "CDP ejecutado"

    apropiacion  = _col_sum(field_values, fn_aprop, idx)
    cdp          = _col_sum(field_values, fn_cdp,   idx)
    obligaciones = _col_sum(field_values, fn_oblig, idx)
    pagos        = _col_sum(field_values, fn_pagos, idx)
    disponible   = _col_sum(field_values, fn_disp,  idx)

    aprop_ref = apropiacion or 1
    pct_cdp   = round(cdp          / aprop_ref * 100, 1)
    pct_oblig = round(obligaciones  / aprop_ref * 100, 1)
    pct_pagos = round(pagos         / aprop_ref * 100, 1)
    pct_disp  = round(disponible    / aprop_ref * 100, 1)

    # % ejecución promedio: promedio de (pagos_rubro / aprop_rubro) por fila
    pct_ejec_vals = []
    if fn_aprop and fn_pagos:
        a_vals = field_values.get(fn_aprop, [])
        p_vals = field_values.get(fn_pagos, [])
        for i in idx:
            try:
                a = float(a_vals[i]) if i < len(a_vals) and a_vals[i] else 0
                p = float(p_vals[i]) if i < len(p_vals) and p_vals[i] else 0
                if a > 0:
                    pct_ejec_vals.append(round(p / a * 100, 1))
            except: pass
    pct_ejec = round(sum(pct_ejec_vals) / len(pct_ejec_vals), 1) if pct_ejec_vals else 0

    # ── KPIs ─────────────────────────────────────────────────────────────────
    # Solo 4 KPIs: Presupuesto inicial, Total ejecutado, Total obligaciones, Total pagos
    kpis = [
        {"label": "Presupuesto inicial",     "value": f"${apropiacion:,.0f}",  "sub": "apropiación definitiva",    "icon": "number"},
        {"label": cdp_label,                 "value": f"${cdp:,.0f}",          "sub": f"{pct_cdp}% del presupuesto","icon": "check"},
        {"label": "Total obligaciones",      "value": f"${obligaciones:,.0f}", "sub": f"{pct_oblig}% del total",   "icon": "number"},
        {"label": "Total pagos",             "value": f"${pagos:,.0f}",        "sub": f"{pct_pagos}% del total",   "icon": "number"},
    ]

    sections = []

    # ── S1 (full): Embudo de ejecución ────────────────────────────────────────
    # Cambiar type a 'bar' para usar dashboard-bar que sí renderiza correctamente
    if apropiacion > 0:
        aprop_ref_local = apropiacion
        sections.append({
            "id": "__ejecucion_progress__",
            "title": "Ejecución presupuestal",
            "subtitle": "Flujo: Apropiación → Compromisos → Obligaciones → Pagos",
            "type": "bar", "span": "full",
            "bars": [
                {"label": "Presupuesto inicial",
                 "value": round(apropiacion),
                 "pct": 100,
                 "color": "#1B3A6B"},
                {"label": cdp_label,
                 "value": round(cdp),
                 "pct": round(cdp / aprop_ref_local * 100, 1),
                 "color": "#2563EB"},
                {"label": "Obligaciones",
                 "value": round(obligaciones),
                 "pct": round(obligaciones / aprop_ref_local * 100, 1),
                 "color": "#0891B2"},
                {"label": "Pagos realizados",
                 "value": round(pagos),
                 "pct": round(pagos / aprop_ref_local * 100, 1),
                 "color": "#059669"},
            ]
        })

    # ── S2 (half): Completeness ───────────────────────────────────────────────
    sections.append({
        "id": "__completeness_presupuesto__",
        "title": "Nivel de ejecución",
        "subtitle": "% sobre presupuesto inicial",
        "type": "completeness", "span": "half",
        "bars": [
            {"label": cdp_label,          "value": pct_cdp,   "pct": pct_cdp,   "color": "#1B3A6B"},
            {"label": "Obligaciones",     "value": pct_oblig, "pct": pct_oblig, "color": "#2563EB"},
            {"label": "Pagos realizados", "value": pct_pagos, "pct": pct_pagos, "color": "#059669"},
        ]
    })

    # ── S3 (half): Donut composición ──────────────────────────────────────────
    obligado_pend = max(obligaciones - pagos, 0)
    segments = []
    if pagos > 0:
        segments.append({"label": "Pagado",             "value": round(pagos),
                          "pct": round(pagos / aprop_ref * 100, 1),         "color": "#059669"})
    if obligado_pend > 0:
        segments.append({"label": "Obligado pendiente", "value": round(obligado_pend),
                          "pct": round(obligado_pend / aprop_ref * 100, 1), "color": "#0891B2"})
    if disponible > 0:
        segments.append({"label": "Disponible",         "value": round(disponible),
                          "pct": round(disponible / aprop_ref * 100, 1),    "color": "#E2E8F0"})
    if segments:
        sections.append({
            "id": "__composicion_presupuesto__",
            "title": "Composición del presupuesto",
            "subtitle": "Pagado · Obligado pendiente · Disponible",
            "type": "donut", "span": "half", "segments": segments,
        })

# ── S4 y S5: Por rubro ────────────────────────────────────────────────────
    if fn_rubro and fn_aprop:
        r_vals = field_values.get(fn_rubro, [])
        a_vals = field_values.get(fn_aprop, [])
        # Obtener p_vals con fallback explícito
        p_vals = field_values.get(fn_pagos, []) if fn_pagos else []

        rubros: dict = {}
        for i in idx:
            r = r_vals[i] if i < len(r_vals) else None
            if not r or str(r).strip() in ("", "nan"): continue
            key = str(r).strip()[:60]
            if key not in rubros:
                rubros[key] = {"aprop": 0.0, "pagos": 0.0}

            # Apropiación
            if i < len(a_vals) and a_vals[i] is not None:
                try: rubros[key]["aprop"] += float(a_vals[i])
                except: pass

            # Pagos — buscar en la columna correcta
            if i < len(p_vals) and p_vals[i] is not None:
                try: rubros[key]["pagos"] += float(p_vals[i])
                except: pass

        if rubros:
            # S4: Apropiación por rubro — usar 'bar' no 'progress'
            bars_aprop = sorted(rubros.items(), key=lambda x: -x[1]["aprop"])
            total_aprop_rubros = sum(v["aprop"] for _, v in bars_aprop) or 1
            sections.append({
                "id": "__por_rubro__",
                "title": "Apropiación por rubro",
                "subtitle": f"{len(bars_aprop)} rubros del proyecto",
                "type": "bar", "span": "full",
                "bars": [
                    {
                        "label": lbl,
                        "value": round(v["aprop"]),
                        "pct": round(v["aprop"] / total_aprop_rubros * 100, 1),
                        "color": COLORS[i % len(COLORS)]
                    }
                    for i, (lbl, v) in enumerate(bars_aprop)
                ]
            })

            # S5: % ejecutado por rubro = pagos / apropiación
            bars_pct = sorted(
                [
                    (lbl, round(v["pagos"] / v["aprop"] * 100, 1) if v["aprop"] > 0 else 0.0)
                    for lbl, v in rubros.items()
                ],
                key=lambda x: -x[1]
            )
            sections.append({
                "id": "__ejecucion_rubro__",
                "title": "% Ejecutado por rubro",
                "subtitle": "Pagos / Apropiación definitiva por rubro",
                "type": "completeness", "span": "full",
                "bars": [
                    {
                        "label": lbl,
                        "value": round(pct, 1),
                        "pct": round(min(pct, 100), 1),
                        "color": COLORS[0] if pct >= 80 else COLORS[5] if pct >= 50 else COLORS[6]
                    }
                    for lbl, pct in bars_pct
                ]
            })

            # S6: Total ejecutado por rubro (valor absoluto de cdp/total_ejecutado)
            if fn_cdp:
                c_vals = field_values.get(fn_cdp, [])
                rubros_cdp: dict = {}
                for i in idx:
                    r = r_vals[i] if i < len(r_vals) else None
                    if not r or str(r).strip() in ("", "nan"): continue
                    key = str(r).strip()[:60]
                    if key not in rubros_cdp:
                        rubros_cdp[key] = 0.0
                    if i < len(c_vals) and c_vals[i] is not None:
                        try: rubros_cdp[key] += float(c_vals[i])
                        except: pass

                if rubros_cdp:
                    bars_cdp = sorted(rubros_cdp.items(), key=lambda x: -x[1])
                    total_cdp_rubros = sum(v for _, v in bars_cdp) or 1
                    sections.append({
                        "id": "__ejecutado_por_rubro__",
                        "title": f"{cdp_label} por actividad",
                        "subtitle": f"Distribución de {cdp_label.lower()} entre {len(bars_cdp)} rubros",
                        "type": "bar", "span": "full",
                        "bars": [
                            {
                                "label": lbl,
                                "value": round(v),
                                "pct": round(v / total_cdp_rubros * 100, 1),
                                "color": COLORS[(i + 2) % len(COLORS)]
                            }
                            for i, (lbl, v) in enumerate(bars_cdp)
                        ]
                    })

            # S7: Total pagos por actividad/rubro (valor absoluto de pagos)
            if fn_pagos:
                rubros_pagos: dict = {}
                for i in idx:
                    r = r_vals[i] if i < len(r_vals) else None
                    if not r or str(r).strip() in ("", "nan"): continue
                    key = str(r).strip()[:60]
                    if key not in rubros_pagos:
                        rubros_pagos[key] = 0.0
                    if i < len(p_vals) and p_vals[i] is not None:
                        try: rubros_pagos[key] += float(p_vals[i])
                        except: pass

                if rubros_pagos:
                    bars_pagos = sorted(rubros_pagos.items(), key=lambda x: -x[1])
                    total_pagos_rubros = sum(v for _, v in bars_pagos) or 1
                    sections.append({
                        "id": "__pagos_por_rubro__",
                        "title": "Total pagos por actividad",
                        "subtitle": f"Distribución de pagos realizados entre {len(bars_pagos)} rubros",
                        "type": "bar", "span": "full",
                        "bars": [
                            {
                                "label": lbl,
                                "value": round(v),
                                "pct": round(v / total_pagos_rubros * 100, 1),
                                "color": COLORS[(i + 4) % len(COLORS)]
                            }
                            for i, (lbl, v) in enumerate(bars_pagos)
                        ]
                    })

    # ── S_GROUPED: Tabla agrupada por Proyecto → actividades PEP ────────────────
    fn_proyecto_code = _fname_exact(fields, "proyecto")
    fn_desc_proyecto = _fname_exact(fields, "descripcion_proyecto")
    fn_pep           = _fname_exact(fields, "descripcion_pep")

    if not fn_proyecto_code: fn_proyecto_code = _fname_all(fields, "proyecto")
    if not fn_desc_proyecto:
        fn_desc_proyecto = next(
            (f.name for f in fields if "descripcion" in norm(f.name) and "proyecto" in norm(f.name)),
            None
        )
    if not fn_pep: fn_pep = _fname_all(fields, "descripcion", "pep")

    if fn_pep and fn_aprop:
        code_vals  = field_values.get(fn_proyecto_code, []) if fn_proyecto_code else []
        dproj_vals = field_values.get(fn_desc_proyecto, []) if fn_desc_proyecto else []
        pep_vals   = field_values.get(fn_pep,   [])
        a_vals2    = field_values.get(fn_aprop,  [])
        cdp_vals2  = field_values.get(fn_cdp,   []) if fn_cdp  else []
        oblig_vals2 = field_values.get(fn_oblig, []) if fn_oblig else []
        pag_vals2  = field_values.get(fn_pagos,  []) if fn_pagos else []
        disp_vals2 = field_values.get(fn_disp,   []) if fn_disp  else []

        # Ordered dict: project_code → {label, activities ordered list}
        from collections import OrderedDict
        projects: "OrderedDict[str, dict]" = OrderedDict()

        for i in idx:
            code    = str(code_vals[i]).strip() if i < len(code_vals) and code_vals[i] else "—"
            d_proj  = str(dproj_vals[i]).strip() if i < len(dproj_vals) and dproj_vals[i] else code
            pep_lbl = str(pep_vals[i]).strip() if i < len(pep_vals) and pep_vals[i] else "Actividad"

            aprop2  = _safe_float(a_vals2,    i)
            cdp2    = _safe_float(cdp_vals2,  i)
            oblig2  = _safe_float(oblig_vals2, i)
            pag2    = _safe_float(pag_vals2,  i)
            disp2   = _safe_float(disp_vals2, i)
            pct2    = round(pag2 / aprop2 * 100, 1) if aprop2 > 0 else 0.0

            if code not in projects:
                projects[code] = {
                    "code": code, "label": d_proj,
                    "aprop": 0.0, "ejecutado": 0.0, "obligaciones": 0.0,
                    "pagos": 0.0, "disponible": 0.0,
                    "activities": []
                }
            g = projects[code]
            g["aprop"]       += aprop2
            g["ejecutado"]   += cdp2
            g["obligaciones"] += oblig2
            g["pagos"]       += pag2
            g["disponible"]  += disp2
            g["activities"].append({
                "label":        pep_lbl,
                "aprop":        round(aprop2),
                "ejecutado":    round(cdp2),
                "obligaciones": round(oblig2),
                "pagos":        round(pag2),
                "disponible":   round(disp2),
                "pct_ejec":     min(pct2, 100.0),
            })

        groups_list = []
        for g in projects.values():
            aprop_g = g["aprop"] or 1
            g["pct_ejec"] = round(min(g["pagos"] / aprop_g * 100, 100.0), 1)
            g["aprop"]       = round(g["aprop"])
            g["ejecutado"]   = round(g["ejecutado"])
            g["obligaciones"] = round(g["obligaciones"])
            g["pagos"]       = round(g["pagos"])
            g["disponible"]  = round(g["disponible"])
            groups_list.append(g)

        if groups_list:
            sections.append({
                "id":    "__detalle_proyectos__",
                "title": "Detalle por proyecto y actividad",
                "subtitle": "Apropiación · Ejecutado · Obligaciones · Pagos · % Ejecución",
                "type": "grouped_rows",
                "span": "full",
                "groups": groups_list,
            })

    return {
        "total": len(idx),
        "kpis": kpis,
        "sections": sections,
        "project_label": "Implementación de la Política Pública de Protección Animal – Un Valle Animalista"
    }