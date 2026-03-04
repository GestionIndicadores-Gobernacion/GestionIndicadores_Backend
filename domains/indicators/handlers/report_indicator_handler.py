from collections import defaultdict
from sqlalchemy.orm import selectinload, joinedload

from domains.indicators.models.Report.report import Report
from domains.indicators.models.Report.report_indicator_value import ReportIndicatorValue


class ReportIndicatorHandler:

    @staticmethod
    def aggregate_indicators_by_component(component_id):
        from domains.indicators.models.Component.component import Component

        component = Component.query.get(component_id)
        if not component:
            from flask import jsonify
            return jsonify({"message": "Componente no encontrado"}), 404

        reports = (
            Report.query
            .options(
                selectinload(Report.indicator_values).joinedload(ReportIndicatorValue.indicator)
            )
            .filter(Report.component_id == component_id)
            .order_by(Report.report_date.asc())
            .all()
        )

        if not reports:
            return {
                "component_id": component_id,
                "indicators": [],
                "by_location": [],
                "by_location_indicator": []
            }

        # ── Acumulador por indicador ─────────────────────────────────────────
        accumulator = defaultdict(lambda: {
            "name": None,
            "field_type": None,
            "by_month": defaultdict(float),
            "by_category": defaultdict(float),
            "by_nested": defaultdict(lambda: defaultdict(float)),
        })

        # ── Acumulador por localización ──────────────────────────────────────
        location_counts = defaultdict(int)
        location_indicator = defaultdict(lambda: defaultdict(float))

        for r in reports:
            month_key = r.report_date.strftime("%Y-%m")

            if r.intervention_location:
                location_counts[r.intervention_location] += 1

            for iv in r.indicator_values:
                indicator = iv.indicator
                if not indicator:
                    continue

                acc = accumulator[iv.indicator_id]
                acc["name"] = indicator.name
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
                    elif isinstance(value, list):
                        for option in value:
                            if isinstance(option, str):
                                acc["by_category"][option] += 1

                # ── categorized_group ────────────────────────────────────────
                elif indicator.field_type == "categorized_group":
                    if isinstance(value, dict):
                        data = value.get("data", {})
                        month_total = 0  # ← nuevo
                        for category, genders in data.items():
                            if isinstance(genders, dict):
                                for gender, metrics in genders.items():
                                    gender_clean = gender.strip().rstrip(',')
                                    if isinstance(metrics, dict):
                                        for metric, val in metrics.items():
                                            if isinstance(val, (int, float)):
                                                acc["by_nested"][category][metric] += val
                                                acc["by_nested"][f"{category} – {gender_clean}"][metric] += val
                                                month_total += val  # ← nuevo

                        acc["by_month"][month_key] += month_total  # ← nuevo

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

        # ── Serializar indicadores ───────────────────────────────────────────
        result = []
        all_months = sorted({r.report_date.strftime("%Y-%m") for r in reports})

        for indicator_id, acc in accumulator.items():
            field_type = acc["field_type"]
            entry = {
                "indicator_id": indicator_id,
                "indicator_name": acc["name"],
                "field_type": field_type,
            }

            if field_type == "number":
                entry["by_month"] = [
                    {"month": m, "total": acc["by_month"].get(m, 0)}
                    for m in all_months
                ]

            elif field_type in ("sum_group", "grouped_data", "select", "multi_select"):
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
                entry["by_month"] = [  # ← nuevo
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

        return {
            "component_id": component_id,
            "indicators": result,
            "by_location": by_location,
            "by_location_indicator": by_location_indicator
        }