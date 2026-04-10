from flask_jwt_extended import get_jwt_identity

from extensions import db
from domains.indicators.models.Report.report import Report, ZoneTypeEnum
from domains.indicators.models.Report.report_indicator_value import ReportIndicatorValue
from domains.indicators.validators.report_validator import ReportValidator
from domains.indicators.models.AuditLog.audit_log import AuditLog
from sqlalchemy.orm import selectinload


def _current_user_is_admin():
    from domains.indicators.models.User.user import User
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return user and user.role and user.role.name == "admin"


class ReportHandler:

    @staticmethod
    def create(data):
        errors = ReportValidator.validate_create(data)
        if errors:
            activity_id = data.get("action_plan_activity_id")  # ← leer ANTES del if
            if "evidence_link" in errors and activity_id:
                from domains.indicators.models.Report.report import Report as ReportModel
                evidence_link = (data.get("evidence_link") or "").strip()
                existing_report = ReportModel.query.filter_by(evidence_link=evidence_link).first()
                if existing_report:
                    result, link_errors = ReportHandler._link_activity_to_report(
                        existing_report, activity_id
                    )
                    if link_errors:
                        return None, link_errors
                    return existing_report, None
            return None, errors

        try:
            user_id = get_jwt_identity()
            activity_id = data.get("action_plan_activity_id")  # ← aquí sigue igual

            report = Report(
                strategy_id=data["strategy_id"],
                component_id=data["component_id"],
                report_date=data["report_date"],
                executive_summary=data["executive_summary"],
                intervention_location=data["intervention_location"],
                zone_type=ZoneTypeEnum(data["zone_type"]),
                evidence_link=data.get("evidence_link"),
                user_id=user_id,
                action_plan_activity_id=activity_id,
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
    def _link_activity_to_report(report, activity_id):
        """Vincula una actividad a un reporte existente."""
        try:
            from domains.action_plans.models.action_plan import ActionPlanActivity
            activity = ActionPlanActivity.query.get(activity_id)
            if not activity:
                return None, {"activity": "Actividad no encontrada."}

            # Verificar que el reporte no tenga ya otra actividad vinculada
            if report.action_plan_activity_id and report.action_plan_activity_id != activity_id:
                return None, {"activity": "Este reporte ya está vinculado a otra actividad."}

            report.action_plan_activity_id = activity_id
            db.session.commit()
            return report, None
        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def update(report, data):
        errors = ReportValidator.validate_create(data, current_report_id=report.id)
        if errors:
            return None, errors

        try:
            user_id = get_jwt_identity()

            report.strategy_id           = data["strategy_id"]
            report.component_id          = data["component_id"]
            report.report_date           = data["report_date"]
            report.executive_summary     = data["executive_summary"]
            report.intervention_location = data["intervention_location"]
            report.zone_type             = ZoneTypeEnum(data["zone_type"])
            report.evidence_link         = data.get("evidence_link")

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
    def get_all(user_id=None, is_admin=False, component_ids=None):
        from sqlalchemy import or_

        query = (
            Report.query
            .options(
                selectinload(Report.indicator_values)
                .joinedload(ReportIndicatorValue.indicator)
            )
        )

        if not is_admin and user_id is not None:
            query = query.filter(
                or_(
                    Report.component_id.in_(component_ids or []),
                    Report.user_id == user_id
                )
            )

        return query.order_by(Report.report_date.desc()).all()
        
    @staticmethod
    def get_by_id(report_id):
        from sqlalchemy.orm import selectinload, joinedload
        return (
            Report.query
            .options(
                selectinload(Report.indicator_values)
                    .joinedload(ReportIndicatorValue.indicator),
                joinedload(Report.component),
                joinedload(Report.strategy),
                joinedload(Report.user),
            )
            .filter(Report.id == report_id)
            .first()
        )

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