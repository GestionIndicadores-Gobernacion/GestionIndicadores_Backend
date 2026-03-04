from flask_jwt_extended import get_jwt_identity

from extensions import db
from domains.indicators.models.Report.report import Report, ZoneTypeEnum
from domains.indicators.models.Report.report_indicator_value import  ReportIndicatorValue
from domains.indicators.validators.report_validator import ReportValidator
from sqlalchemy import func
from collections import defaultdict

from domains.indicators.models.AuditLog.audit_log import AuditLog

from sqlalchemy.orm import joinedload, selectinload

def _current_user_is_admin():
    """Devuelve True si el usuario JWT actual tiene rol admin."""
    from domains.indicators.models.User.user import User
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return user and user.role and user.role.name == "admin"


class ReportHandler:

    @staticmethod
    def create(data):
        errors = ReportValidator.validate_create(data)
        if errors:
            return None, errors

        try:
            user_id = get_jwt_identity()

            report = Report(
                strategy_id=data["strategy_id"],
                component_id=data["component_id"],
                report_date=data["report_date"],
                executive_summary=data["executive_summary"],
                activities_performed=data["activities_performed"],
                intervention_location=data["intervention_location"],
                zone_type=ZoneTypeEnum(data["zone_type"]),
                evidence_link=data.get("evidence_link"),
                user_id=user_id,
            )
            db.session.add(report)
            db.session.flush()

            for val in data["indicator_values"]:
                db.session.add(ReportIndicatorValue(
                    report_id=report.id,
                    indicator_id=val["indicator_id"],
                    value=val["value"]
                ))

            db.session.add(AuditLog(
                user_id=user_id,
                entity="report",
                entity_id=report.id,
                action="created"
            ))

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
            user_id = get_jwt_identity()

            report.strategy_id            = data["strategy_id"]
            report.component_id           = data["component_id"]
            report.report_date            = data["report_date"]
            report.executive_summary      = data["executive_summary"]
            report.activities_performed   = data["activities_performed"]
            report.intervention_location  = data["intervention_location"]
            report.zone_type              = ZoneTypeEnum(data["zone_type"])
            report.evidence_link          = data.get("evidence_link")

            existing_map = {iv.indicator_id: iv for iv in report.indicator_values}
            for val in data["indicator_values"]:
                indicator_id = val["indicator_id"]
                if indicator_id in existing_map:
                    existing_map[indicator_id].value = val["value"]
                else:
                    report.indicator_values.append(
                        ReportIndicatorValue(indicator_id=indicator_id, value=val["value"])
                    )

            db.session.add(AuditLog(
                user_id=user_id,
                entity="report",
                entity_id=report.id,
                action="updated"
            ))

            db.session.commit()
            return report, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def get_all():
        user_id = get_jwt_identity()

        if _current_user_is_admin():
            return Report.query.order_by(Report.report_date.desc()).all()

        # Usuarios normales: ven los suyos + los que no tienen dueño
        return (
            Report.query
            .filter(
                (Report.user_id == user_id) | (Report.user_id == None)
            )
            .order_by(Report.report_date.desc())
            .all()
        )

    @staticmethod
    def get_by_id(report_id):
        return Report.query.get(report_id)

    @staticmethod
    def delete(report):
        try:
            user_id = get_jwt_identity()
            db.session.add(AuditLog(
                user_id=user_id,
                entity="report",
                entity_id=report.id,
                action="deleted",
                detail=f"report_date={report.report_date}"
            ))
            db.session.delete(report)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    # =========================================================
    # AGGREGATE BY STRATEGY
    # =========================================================
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
        
    # =========================================================
    # AGGREGATE INDICATORS BY COMPONENT
    # =========================================================
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
            return {"component_id": component_id, "indicators": []}

        # Acumulador por indicador
        accumulator = defaultdict(lambda: {
            "name": None,
            "field_type": None,
            "by_month": defaultdict(float),       # month -> total  (number)
            "by_category": defaultdict(float),    # category -> total (sum_group, select, multi_select)
            "by_nested": defaultdict(             # category -> metric -> total (categorized_group, grouped_data)
                lambda: defaultdict(float)
            ),
        })

        for r in reports:
            month_key = r.report_date.strftime("%Y-%m")

            for iv in r.indicator_values:
                indicator = iv.indicator
                if not indicator:
                    continue

                acc = accumulator[iv.indicator_id]
                acc["name"] = indicator.name
                acc["field_type"] = indicator.field_type
                value = iv.value

                # ── number ──────────────────────────────────────────────────
                if indicator.field_type == "number":
                    if isinstance(value, (int, float)):
                        acc["by_month"][month_key] += value

                # ── sum_group ────────────────────────────────────────────────
                # {"GUIAS TURISTICOS": 5, "MONITORES": 8}
                elif indicator.field_type == "sum_group":
                    if isinstance(value, dict):
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
                # {"selected_categories": [...], "data": {CAT: {Genero: {metric: val}}}, "sub_sections": {...}}
                elif indicator.field_type == "categorized_group":
                    if isinstance(value, dict):
                        data = value.get("data", {})
                        for category, genders in data.items():
                            if isinstance(genders, dict):
                                for gender, metrics in genders.items():
                                    if isinstance(metrics, dict):
                                        for metric, val in metrics.items():
                                            if isinstance(val, (int, float)):
                                                key = f"{category} – {metric}"
                                                acc["by_nested"][category][metric] += val

                        # sub_sections también
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
                        for group, val in value.items():
                            if isinstance(val, (int, float)):
                                acc["by_category"][group] += val

        # ── Serializar ───────────────────────────────────────────────────────
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

            elif field_type == "categorized_group":
                entry["by_nested"] = {
                    category: [
                        {"metric": metric, "total": round(total, 2)}
                        for metric, total in metrics.items()
                    ]
                    for category, metrics in acc["by_nested"].items()
                }

            result.append(entry)

        return {"component_id": component_id, "indicators": result}