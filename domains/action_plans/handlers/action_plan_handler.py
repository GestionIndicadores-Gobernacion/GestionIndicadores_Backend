from flask_jwt_extended import get_jwt_identity
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import uuid

from extensions import db
from domains.action_plans.models.action_plan import (
    ActionPlan, ActionPlanObjective, ActionPlanActivity, ActionPlanSupportStaff
)
from domains.action_plans.validators.action_plan_validator import ActionPlanValidator
from domains.indicators.models.AuditLog.audit_log import AuditLog
from sqlalchemy.orm import selectinload


def _generate_dates(start_date: date, recurrence: dict) -> list[date]:
    """
    Genera una lista de fechas según la regla de recurrencia.
    recurrence = {
        "frequency": "daily"|"weekly"|"biweekly"|"monthly"|"yearly"|"custom",
        "until": "YYYY-MM-DD",          # fecha límite
        "day_of_month": 26,             # para monthly
        "day_of_week": 0,               # 0=lun..6=dom, para weekly/biweekly
        "interval": 3,                  # para custom (cada N días)
    }
    """
    frequency = recurrence.get("frequency")
    until_str = recurrence.get("until")
    if not until_str:
        return [start_date]

    until = date.fromisoformat(until_str)
    dates = []
    current = start_date

    while current <= until:
        dates.append(current)

        if frequency == "daily":
            current = current + timedelta(days=1)

        elif frequency == "weekly":
            current = current + timedelta(weeks=1)

        elif frequency == "biweekly":
            current = current + timedelta(weeks=2)

        elif frequency == "monthly":
            # Mismo día del mes cada mes
            next_month = current + relativedelta(months=1)
            day = recurrence.get("day_of_month", current.day)
            try:
                current = next_month.replace(day=day)
            except ValueError:
                # Día no existe en ese mes (ej: 31 de febrero)
                import calendar
                last_day = calendar.monthrange(next_month.year, next_month.month)[1]
                current = next_month.replace(day=last_day)

        elif frequency == "yearly":
            current = current + relativedelta(years=1)

        elif frequency == "custom":
            interval = recurrence.get("interval", 7)
            current = current + timedelta(days=interval)

        else:
            break

    return dates


class ActionPlanHandler:

    @staticmethod
    def create(data):
        errors = ActionPlanValidator.validate_create(data)
        if errors:
            return None, errors

        try:
            user_id = get_jwt_identity()
            objectives_data = data.pop("plan_objectives", [])

            plan = ActionPlan(
                strategy_id  = data["strategy_id"],
                component_id = data["component_id"],
                responsible  = (data.get("responsible") or "").strip() or None,
                user_id      = user_id,
            )
            db.session.add(plan)
            db.session.flush()

            for obj_data in objectives_data:
                plan_obj = ActionPlanObjective(
                    action_plan_id = plan.id,
                    objective_id   = obj_data.get("objective_id"),
                    objective_text = (obj_data.get("objective_text") or "").strip() or None,
                )
                db.session.add(plan_obj)
                db.session.flush()

                for act_data in obj_data.get("activities", []):
                    recurrence = act_data.get("recurrence")

                    # Generar fechas si hay recurrencia
                    base_date = act_data["delivery_date"]
                    if isinstance(base_date, str):
                        base_date = date.fromisoformat(base_date)
                    elif hasattr(base_date, 'isoformat'):
                        pass  # ya es date, no hacer nada

                    if recurrence:
                        dates = _generate_dates(base_date, recurrence)
                        group_id = str(uuid.uuid4())
                    else:
                        dates = [base_date]
                        group_id = None

                    for delivery_date in dates:
                        activity = ActionPlanActivity(
                            plan_objective_id        = plan_obj.id,
                            name                     = act_data["name"].strip(),
                            deliverable              = act_data["deliverable"].strip(),
                            delivery_date            = delivery_date,
                            requires_boss_assistance = act_data.get("requires_boss_assistance", False),
                            recurrence_group_id      = group_id,
                            recurrence_rule          = recurrence,
                        )
                        db.session.add(activity)
                        db.session.flush()

                        for staff in act_data.get("support_staff", []):
                            db.session.add(ActionPlanSupportStaff(
                                activity_id = activity.id,
                                name        = (staff.get("name") or "").strip()
                            ))

            db.session.add(AuditLog(
                user_id=user_id,
                entity="action_plan",
                entity_id=plan.id,
                action="created"
            ))

            db.session.commit()
            return plan, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def get_all(strategy_id=None, component_id=None, month=None, year=None):
        query = ActionPlan.query

        if strategy_id:
            query = query.filter(ActionPlan.strategy_id == strategy_id)
        if component_id:
            query = query.filter(ActionPlan.component_id == component_id)

        if month and year:
            from domains.action_plans.models.action_plan import ActionPlanObjective as APO
            start_date = date(year, month, 1)
            end_date   = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            query = (
                query
                .join(APO)
                .join(ActionPlanActivity)
                .filter(
                    ActionPlanActivity.delivery_date >= start_date,
                    ActionPlanActivity.delivery_date <  end_date
                )
                .distinct()
            )

        return query.order_by(ActionPlan.id.asc()).all()

    @staticmethod
    def get_by_id(plan_id):
        return ActionPlan.query.get(plan_id)

    @staticmethod
    def report_activity(activity_id, data):
        activity = ActionPlanActivity.query.get(activity_id)
        if not activity:
            return None, {"activity": "Actividad no encontrada."}

        errors = ActionPlanValidator.validate_report(data, activity)
        if errors:
            return None, errors

        try:
            user_id = get_jwt_identity()
            now = datetime.utcnow()

            activity.evidence_url        = (data.get("evidence_url") or "").strip()
            activity.description         = (data.get("description") or "").strip() or None
            activity.reported_at         = now
            activity.score               = 5 if now.date() <= activity.delivery_date else 1
            activity.reported_by_user_id = int(user_id)

            plan_id = activity.plan_objective.action_plan_id
            db.session.add(AuditLog(
                user_id=user_id,
                entity="action_plan",
                entity_id=plan_id,
                action="updated",
                detail=f"Actividad #{activity_id} reportada — score={activity.score}"
            ))

            db.session.commit()
            return activity, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def update_activity(activity_id, data, edit_all=False):
        """
        Edita una actividad o todas las del grupo de recurrencia.
        edit_all=True → edita nombre, entregable, requires_boss_assistance de todo el grupo.
        edit_all=False → edita solo esta actividad (incluye fecha).
        """
        activity = ActionPlanActivity.query.get(activity_id)
        if not activity:
            return None, {"activity": "Actividad no encontrada."}

        try:
            user_id = get_jwt_identity()

            if edit_all and activity.recurrence_group_id:
                # Editar todas las del grupo (excepto las ya reportadas)
                group = ActionPlanActivity.query.filter_by(
                    recurrence_group_id=activity.recurrence_group_id
                ).filter(ActionPlanActivity.evidence_url.is_(None)).all()

                for act in group:
                    act.name                     = data["name"].strip()
                    act.deliverable              = data["deliverable"].strip()
                    act.requires_boss_assistance = data.get("requires_boss_assistance", act.requires_boss_assistance)

                    # Actualizar support_staff si viene
                    if "support_staff" in data:
                        for s in act.support_staff:
                            db.session.delete(s)
                        db.session.flush()
                        for staff in data["support_staff"]:
                            db.session.add(ActionPlanSupportStaff(
                                activity_id=act.id,
                                name=(staff.get("name") or "").strip()
                            ))
            else:
                # Editar solo esta
                activity.name                     = data["name"].strip()
                activity.deliverable              = data["deliverable"].strip()
                activity.requires_boss_assistance = data.get("requires_boss_assistance", activity.requires_boss_assistance)

                if "delivery_date" in data:
                    d = data["delivery_date"]
                    activity.delivery_date = date.fromisoformat(str(d)) if isinstance(d, str) else d

                if "support_staff" in data:
                    for s in activity.support_staff:
                        db.session.delete(s)
                    db.session.flush()
                    for staff in data["support_staff"]:
                        db.session.add(ActionPlanSupportStaff(
                            activity_id=activity.id,
                            name=(staff.get("name") or "").strip()
                        ))

            plan_id = activity.plan_objective.action_plan_id
            db.session.add(AuditLog(
                user_id=user_id,
                entity="action_plan",
                entity_id=plan_id,
                action="updated",
                detail=f"Actividad #{activity_id} editada — edit_all={edit_all}"
            ))

            db.session.commit()
            return activity, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def delete(plan_id):
        plan = ActionPlanHandler.get_by_id(plan_id)
        if not plan:
            return False, {"plan": "Plan de acción no encontrado."}
        try:
            user_id = get_jwt_identity()
            db.session.add(AuditLog(
                user_id=user_id,
                entity="action_plan",
                entity_id=plan_id,
                action="deleted"
            ))
            db.session.delete(plan)
            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, {"database": str(e)}

    @staticmethod
    def delete_activity(activity_id, delete_all=False):
        activity = ActionPlanActivity.query.get(activity_id)
        if not activity:
            return False, {"activity": "Actividad no encontrada."}
        try:
            if delete_all and activity.recurrence_group_id:
                # Eliminar todas las no reportadas del grupo
                group = ActionPlanActivity.query.filter_by(
                    recurrence_group_id=activity.recurrence_group_id
                ).filter(ActionPlanActivity.evidence_url.is_(None)).all()
                for act in group:
                    db.session.delete(act)
            else:
                plan_obj = activity.plan_objective
                db.session.delete(activity)
                db.session.flush()

                if len(plan_obj.activities) == 0:
                    plan = plan_obj.action_plan
                    db.session.delete(plan_obj)
                    db.session.flush()

                    if len(plan.plan_objectives) == 0:
                        db.session.delete(plan)

            db.session.commit()
            return True, None
        except Exception as e:
            db.session.rollback()
            return False, {"database": str(e)}