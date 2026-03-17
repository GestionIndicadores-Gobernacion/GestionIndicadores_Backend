from collections import defaultdict
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import extract

from domains.indicators.models.Report.report import Report
from domains.indicators.models.Report.report_indicator_value import ReportIndicatorValue


# ── Cross-indicator config ────────────────────────────────────────────
# { component_id: [(text_indicator_id, number_indicator_id, virtual_indicator_id, label)] }
CROSS_INDICATOR_CONFIG: dict[int, list[tuple]] = {
    24: [
        (116, 117, -6001, "Cantidad de jóvenes inscritos / institución educativa"),
    ],
    25: [
        (120, 121, -8001, "Temas tratados / foros"),
    ],
    26: [
        (146, 147, -7002, "Cantidad de personas / experiencia"),
    ],
}

class ReportIndicatorHandler:

    @staticmethod
    def aggregate_indicators_by_component(component_id, year: int = None):
        from domains.indicators.models.Component.component import Component

        component = Component.query.get(component_id)
        if not component:
            from flask import jsonify
            return jsonify({"message": "Componente no encontrado"}), 404

        query = (
            Report.query
            .options(
                selectinload(Report.indicator_values).joinedload(ReportIndicatorValue.indicator)
            )
            .filter(Report.component_id == component_id)
        )

        if year:
            query = query.filter(extract('year', Report.report_date) == year)

        reports = query.order_by(Report.report_date.asc()).all()

        if not reports:
            return {
                "component_id": component_id,
                "indicators": [],
                "by_location": [],
                "by_location_indicator": [],
                "by_actor_location": []
            }

        # ── Cargar records de datasets usados por indicadores dataset_select ─
        from domains.indicators.models.Component.component_indicator import ComponentIndicator
        from domains.datasets.models.record import Record
        from domains.datasets.models.table import Table

        ds_indicators = ComponentIndicator.query.filter_by(
            component_id=component_id
        ).filter(
            ComponentIndicator.field_type.in_(["dataset_select", "dataset_multi_select"])
        ).all()

        dataset_record_map: dict[int, dict[int, dict]] = {}

        for ds_ind in ds_indicators:
            cfg        = ds_ind.config or {}
            dataset_id = cfg.get("dataset_id")
            if not dataset_id or dataset_id in dataset_record_map:
                continue
            tables    = Table.query.filter_by(dataset_id=dataset_id).all()
            table_ids = [t.id for t in tables]
            if not table_ids:
                continue
            records = Record.query.filter(Record.table_id.in_(table_ids)).all()
            dataset_record_map[dataset_id] = {r.id: r.data for r in records}

        # ── Acumulador por indicador ─────────────────────────────────────────
        accumulator = defaultdict(lambda: {
            "name": None,
            "field_type": None,
            "by_month": defaultdict(float),
            "by_category": defaultdict(float),
            "by_nested": defaultdict(lambda: defaultdict(float)),
        })

        # ── Acumulador por localización ──────────────────────────────────────
        location_counts    = defaultdict(int)
        location_indicator = defaultdict(lambda: defaultdict(float))

        # ── Acumulador actor por localización ────────────────────────────────
        actor_location_acc: dict[int, dict[str, dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(int))
        )

        # ── Mapa report_id -> {indicator_id -> value} para cruces ────────────
        report_value_map: dict[int, dict[int, any]] = defaultdict(dict)

        for r in reports:
            month_key = r.report_date.strftime("%Y-%m")

            if r.intervention_location:
                location_counts[r.intervention_location] += 1

            for iv in r.indicator_values:
                indicator = iv.indicator
                if not indicator:
                    continue

                # Guardar valor para cruces
                report_value_map[r.id][iv.indicator_id] = iv.value

                acc   = accumulator[iv.indicator_id]
                acc["name"]       = indicator.name
                acc["field_type"] = indicator.field_type
                value = iv.value

                # ── number ───────────────────────────────────────────────────
                if indicator.field_type == "number":
                    if isinstance(value, (int, float)):
                        acc["by_month"][month_key] += value
                        if r.intervention_location:
                            location_indicator[r.intervention_location][iv.indicator_id] += value

                # ── sum_group ────────────────────────────────────────────────
                elif indicator.field_type == "sum_group":
                    if isinstance(value, dict):
                        month_total = sum(v for v in value.values() if isinstance(v, (int, float)))
                        acc["by_month"][month_key] += month_total
                        for category, total in value.items():
                            if isinstance(total, (int, float)):
                                acc["by_category"][category] += total

                # ── select / multi_select ────────────────────────────────────
                elif indicator.field_type in ("select", "multi_select"):
                    if isinstance(value, str):
                        acc["by_category"][value] += 1
                        acc["by_month"][month_key] += 1
                    elif isinstance(value, list):
                        for option in value:
                            if isinstance(option, str):
                                acc["by_category"][option] += 1
                        acc["by_month"][month_key] += 1

                # ── categorized_group ────────────────────────────────────────
                elif indicator.field_type == "categorized_group":
                    if isinstance(value, dict):
                        data        = value.get("data", {})
                        month_total = 0
                        for category, genders in data.items():
                            if isinstance(genders, dict):
                                for gender, metrics in genders.items():
                                    gender_clean = gender.strip().rstrip(',')
                                    if isinstance(metrics, dict):
                                        for metric, val in metrics.items():
                                            if isinstance(val, (int, float)):
                                                acc["by_nested"][category][metric] += val
                                                acc["by_nested"][f"{category} – {gender_clean}"][metric] += val
                                                month_total += val

                        acc["by_month"][month_key] += month_total

                        sub = value.get("sub_sections", {})
                        if isinstance(sub, dict):
                            for section, metrics in sub.items():
                                if isinstance(metrics, dict):
                                    for metric, val in metrics.items():
                                        if isinstance(val, (int, float)):
                                            acc["by_nested"][f"sub:{section}"][metric] += val

                # ── grouped_data ─────────────────────────────────────────────
                elif indicator.field_type == "grouped_data":
                    if isinstance(value, dict):
                        month_total = sum(v for v in value.values() if isinstance(v, (int, float)))
                        acc["by_month"][month_key] += month_total
                        for group, val in value.items():
                            if isinstance(val, (int, float)):
                                acc["by_category"][group] += val

                # ── dataset_select ───────────────────────────────────────────
                elif indicator.field_type == "dataset_select":
                    if isinstance(value, int):
                        cfg        = indicator.config or {}
                        dataset_id = cfg.get("dataset_id")
                        record_data = dataset_record_map.get(dataset_id, {}).get(value, {})

                        label = (
                            record_data.get("nombre")
                            or record_data.get("albergue_o_fundación")
                            or str(value)
                        )
                        acc["by_category"][label] += 1
                        acc["by_month"][month_key] += 1

                        if r.intervention_location:
                            actor_location_acc[iv.indicator_id][r.intervention_location][label] += 1

                # ── dataset_multi_select ─────────────────────────────────────
                elif indicator.field_type == "dataset_multi_select":
                    if isinstance(value, list):
                        cfg        = indicator.config or {}
                        dataset_id = cfg.get("dataset_id")
                        record_lookup = dataset_record_map.get(dataset_id, {})

                        for record_id in value:
                            if not isinstance(record_id, int):
                                continue
                            record_data = record_lookup.get(record_id, {})
                            label = (
                                record_data.get("nombre")
                                or record_data.get("albergue_o_fundación")
                                or str(record_id)
                            )
                            acc["by_category"][label] += 1
                            if r.intervention_location:
                                actor_location_acc[iv.indicator_id][r.intervention_location][label] += 1

                        acc["by_month"][month_key] += 1

        # ── Serializar indicadores ───────────────────────────────────────────
        result     = []
        all_months = sorted({r.report_date.strftime("%Y-%m") for r in reports})

        # ── Cruces texto x número ────────────────────────────────────────────
        if component_id in CROSS_INDICATOR_CONFIG:
            for (text_id, number_id, virtual_id, label) in CROSS_INDICATOR_CONFIG[component_id]:
                bucket: dict[str, float] = defaultdict(float)

                for r in reports:
                    vals   = report_value_map[r.id]
                    nombre = vals.get(text_id)
                    amount = vals.get(number_id)
                    if isinstance(nombre, str) and nombre.strip() and isinstance(amount, (int, float)):
                        bucket[nombre.strip()] += amount

                if bucket:
                    result.append({
                        "indicator_id":   virtual_id,
                        "indicator_name": label,
                        "field_type":     "by_category_cross",
                        "by_category": [
                            {"category": cat, "total": round(total, 2)}
                            for cat, total in sorted(bucket.items(), key=lambda x: -x[1])
                        ]
                    })

        for indicator_id, acc in accumulator.items():
            field_type = acc["field_type"]
            entry = {
                "indicator_id":   indicator_id,
                "indicator_name": acc["name"],
                "field_type":     field_type,
            }

            if field_type == "number":
                entry["by_month"] = [
                    {"month": m, "total": acc["by_month"].get(m, 0)}
                    for m in all_months
                ]

            elif field_type in ("sum_group", "grouped_data", "select", "multi_select",
                                "dataset_select", "dataset_multi_select"):
                entry["by_category"] = [
                    {"category": cat, "total": round(total, 2)}
                    for cat, total in sorted(acc["by_category"].items(), key=lambda x: -x[1])
                ]
                entry["by_month"] = [
                    {"month": m, "total": acc["by_month"].get(m, 0)}
                    for m in all_months
                ]

            elif field_type == "categorized_group":
                entry["by_nested"] = {
                    category: [
                        {"metric": metric, "total": round(total, 2)}
                        for metric, total in metrics.items()
                    ]
                    for category, metrics in acc["by_nested"].items()
                }
                entry["by_month"] = [
                    {"month": m, "total": acc["by_month"].get(m, 0)}
                    for m in all_months
                ]

            result.append(entry)

        # ── Serializar by_location ───────────────────────────────────────────
        by_location = [
            {"location": loc, "total": count}
            for loc, count in sorted(location_counts.items(), key=lambda x: -x[1])
        ]

        # ── Serializar by_location_indicator ────────────────────────────────
        by_location_indicator = [
            {
                "location": loc,
                "indicators": [
                    {"indicator_id": ind_id, "total": round(total, 2)}
                    for ind_id, total in indicators.items()
                ]
            }
            for loc, indicators in sorted(location_indicator.items())
        ]

        # ── Serializar by_actor_location ─────────────────────────────────────
        by_actor_location = []
        for indicator_id, locations in actor_location_acc.items():
            ind_name = accumulator[indicator_id]["name"] if indicator_id in accumulator else str(indicator_id)
            by_actor_location.append({
                "indicator_id":   indicator_id,
                "indicator_name": ind_name,
                "by_location": [
                    {
                        "location": loc,
                        "actors": [
                            {"actor": actor, "count": count}
                            for actor, count in sorted(actors.items(), key=lambda x: -x[1])
                        ]
                    }
                    for loc, actors in sorted(locations.items())
                ]
            })

        return {
            "component_id":          component_id,
            "indicators":            result,
            "by_location":           by_location,
            "by_location_indicator": by_location_indicator,
            "by_actor_location":     by_actor_location,
        }