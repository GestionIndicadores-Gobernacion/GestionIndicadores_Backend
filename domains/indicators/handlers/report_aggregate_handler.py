from collections import defaultdict
from sqlalchemy.orm import joinedload, selectinload

from domains.indicators.models.Report.report import Report
from domains.indicators.models.Report.report_indicator_value import ReportIndicatorValue


class ReportAggregateHandler:

    @staticmethod
    def aggregate_by_strategy(strategy_id):
        reports = (
            Report.query
            .options(
                joinedload(Report.component),
                selectinload(Report.indicator_values).joinedload(ReportIndicatorValue.indicator)
            )
            .filter(Report.strategy_id == strategy_id)
            .order_by(Report.report_date.asc())
            .all()
        )

        if not reports:
            return {
                "strategy_id": strategy_id,
                "total_reports": 0,
                "by_zone": {"Urbana": 0, "Rural": 0},
                "by_component": [],
                "by_month": []
            }

        by_zone = {"Urbana": 0, "Rural": 0}
        for r in reports:
            by_zone[r.zone_type.value] += 1

        component_counts = defaultdict(int)
        component_names = {}
        for r in reports:
            component_counts[r.component_id] += 1
            if r.component_id not in component_names:
                component_names[r.component_id] = (
                    r.component.name if r.component else str(r.component_id)
                )

        by_component = [
            {"component_id": cid, "component_name": component_names[cid], "total": count}
            for cid, count in sorted(component_counts.items())
        ]

        month_data = defaultdict(lambda: {"total": 0, "Urbana": 0, "Rural": 0})
        for r in reports:
            key = r.report_date.strftime("%Y-%m")
            month_data[key]["total"] += 1
            month_data[key][r.zone_type.value] += 1

        by_month = [
            {"month": month, "total": data["total"], "urbana": data["Urbana"], "rural": data["Rural"]}
            for month, data in sorted(month_data.items())
        ]

        return {
            "strategy_id": strategy_id,
            "total_reports": len(reports),
            "by_zone": by_zone,
            "by_component": by_component,
            "by_month": by_month
        }

    @staticmethod
    def aggregate_by_component(component_id):
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
                "total_reports": 0,
                "by_zone": {"Urbana": 0, "Rural": 0},
                "by_month": [],
                "indicator_summary": []
            }

        by_zone = {"Urbana": 0, "Rural": 0}
        for r in reports:
            by_zone[r.zone_type.value] += 1

        month_data = defaultdict(lambda: {"total": 0, "Urbana": 0, "Rural": 0})
        for r in reports:
            key = r.report_date.strftime("%Y-%m")
            month_data[key]["total"] += 1
            month_data[key][r.zone_type.value] += 1

        by_month = [
            {"month": month, "total": data["total"], "urbana": data["Urbana"], "rural": data["Rural"]}
            for month, data in sorted(month_data.items())
        ]

        indicator_accumulator = defaultdict(lambda: {"values": [], "name": None, "field_type": None})
        for r in reports:
            for iv in r.indicator_values:
                indicator = iv.indicator
                if indicator and indicator.field_type == "number":
                    acc = indicator_accumulator[iv.indicator_id]
                    acc["name"] = indicator.name
                    acc["field_type"] = indicator.field_type
                    if isinstance(iv.value, (int, float)):
                        acc["values"].append(iv.value)

        indicator_summary = []
        for indicator_id, acc in indicator_accumulator.items():
            values = acc["values"]
            if not values:
                continue
            indicator_summary.append({
                "indicator_id": indicator_id,
                "indicator_name": acc["name"],
                "field_type": acc["field_type"],
                "total": round(sum(values), 2),
                "average": round(sum(values) / len(values), 2),
                "report_count": len(values)
            })

        return {
            "component_id": component_id,
            "total_reports": len(reports),
            "by_zone": by_zone,
            "by_month": by_month,
            "indicator_summary": indicator_summary
        }