from extensions import db
from domains.indicators.models.Report.report import Report, ZoneTypeEnum
from domains.indicators.models.Report.report_indicator_value import  ReportIndicatorValue
from domains.indicators.validators.report_validator import ReportValidator
from sqlalchemy import func
from collections import defaultdict


class ReportHandler:

    @staticmethod
    def create(data):
        errors = ReportValidator.validate_create(data)
        if errors:
            return None, errors

        try:
            report = Report(
                strategy_id=data["strategy_id"],
                component_id=data["component_id"],
                report_date=data["report_date"],
                executive_summary=data["executive_summary"],
                activities_performed=data["activities_performed"],
                intervention_location=data["intervention_location"],
                zone_type=ZoneTypeEnum(data["zone_type"]),
                evidence_link=data.get("evidence_link")
            )

            db.session.add(report)
            db.session.flush()

            for val in data["indicator_values"]:
                db.session.add(
                    ReportIndicatorValue(
                        report_id=report.id,
                        indicator_id=val["indicator_id"],
                        value=val["value"]
                    )
                )

            db.session.commit()
            return report, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def update(report, data):
        errors = ReportValidator.validate_create(data)
        if errors:
            return None, errors

        try:
            report.strategy_id = data["strategy_id"]
            report.component_id = data["component_id"]
            report.report_date = data["report_date"]
            report.executive_summary = data["executive_summary"]
            report.activities_performed = data["activities_performed"]
            report.intervention_location = data["intervention_location"]
            report.zone_type = ZoneTypeEnum(data["zone_type"])
            report.evidence_link = data.get("evidence_link")

            # Upsert por indicator_id en lugar de clear() + reinsert
            # Así los indicator_values que no vienen en el payload se preservan
            existing_map = {iv.indicator_id: iv for iv in report.indicator_values}

            for val in data["indicator_values"]:
                indicator_id = val["indicator_id"]
                if indicator_id in existing_map:
                    # Actualizar valor existente
                    existing_map[indicator_id].value = val["value"]
                else:
                    # Agregar nuevo valor
                    report.indicator_values.append(
                        ReportIndicatorValue(
                            indicator_id=indicator_id,
                            value=val["value"]
                        )
                    )

            db.session.commit()
            return report, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def get_all():
        return Report.query.order_by(Report.report_date.desc()).all()

    @staticmethod
    def get_by_id(report_id):
        return Report.query.get(report_id)

    @staticmethod
    def delete(report):
        db.session.delete(report)
        db.session.commit()

    # =========================================================
    # AGGREGATE BY STRATEGY
    # =========================================================
    @staticmethod
    def aggregate_by_strategy(strategy_id):
        reports = (
            Report.query
            .filter_by(strategy_id=strategy_id)
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

        # --- by_zone ---
        by_zone = {"Urbana": 0, "Rural": 0}
        for r in reports:
            by_zone[r.zone_type.value] += 1

        # --- by_component ---
        component_counts = defaultdict(int)
        component_names = {}
        for r in reports:
            component_counts[r.component_id] += 1
            if r.component_id not in component_names:
                component_names[r.component_id] = (
                    r.component.name if r.component else str(r.component_id)
                )

        by_component = [
            {
                "component_id": cid,
                "component_name": component_names[cid],
                "total": count
            }
            for cid, count in sorted(component_counts.items())
        ]

        # --- by_month (usando report_date) ---
        month_data = defaultdict(lambda: {"total": 0, "Urbana": 0, "Rural": 0})
        for r in reports:
            key = r.report_date.strftime("%Y-%m")
            month_data[key]["total"] += 1
            month_data[key][r.zone_type.value] += 1

        by_month = [
            {
                "month": month,
                "total": data["total"],
                "urbana": data["Urbana"],
                "rural": data["Rural"]
            }
            for month, data in sorted(month_data.items())
        ]

        return {
            "strategy_id": strategy_id,
            "total_reports": len(reports),
            "by_zone": by_zone,
            "by_component": by_component,
            "by_month": by_month
        }

    # =========================================================
    # AGGREGATE BY COMPONENT
    # =========================================================
    @staticmethod
    def aggregate_by_component(component_id):
        reports = (
            Report.query
            .filter_by(component_id=component_id)
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

        # --- by_zone ---
        by_zone = {"Urbana": 0, "Rural": 0}
        for r in reports:
            by_zone[r.zone_type.value] += 1

        # --- by_month ---
        month_data = defaultdict(lambda: {"total": 0, "Urbana": 0, "Rural": 0})
        for r in reports:
            key = r.report_date.strftime("%Y-%m")
            month_data[key]["total"] += 1
            month_data[key][r.zone_type.value] += 1

        by_month = [
            {
                "month": month,
                "total": data["total"],
                "urbana": data["Urbana"],
                "rural": data["Rural"]
            }
            for month, data in sorted(month_data.items())
        ]

        # --- indicator_summary (solo field_type == "number") ---
        indicator_accumulator = defaultdict(lambda: {
            "values": [],
            "name": None,
            "field_type": None
        })

        for r in reports:
            for iv in r.indicator_values:
                indicator = iv.indicator  # relación backref
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