from datetime import datetime, date
from extensions import db
from flask_jwt_extended import get_jwt_identity

from domains.action_plans.models.action_plan import (
    ActionPlan, ActionPlanObjective, ActionPlanActivity, ActionPlanSupportStaff
)
from domains.action_plans.validators.action_plan_validator import ActionPlanValidator
from domains.indicators.models.AuditLog.audit_log import AuditLog


def _current_user_is_admin():
    from domains.indicators.models.User.user import User
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    return user and user.role and user.role.name == "admin"


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
                    activity = ActionPlanActivity(
                        plan_objective_id        = plan_obj.id,
                        name                     = act_data["name"].strip(),
                        deliverable              = act_data["deliverable"].strip(),
                        delivery_date            = act_data["delivery_date"],
                        requires_boss_assistance = act_data.get("requires_boss_assistance", False),
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
        user_id = get_jwt_identity()
        query = ActionPlan.query

        if not _current_user_is_admin():
            # Ven los suyos + los que no tienen dueño
            query = query.filter(
                (ActionPlan.user_id == user_id) | (ActionPlan.user_id == None)
            )

        if strategy_id:
            query = query.filter(ActionPlan.strategy_id == strategy_id)
        if component_id:
            query = query.filter(ActionPlan.component_id == component_id)

        if month and year:
            start_date = date(year, month, 1)
            end_date   = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            query = (
                query
                .join(ActionPlanObjective)
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

            activity.evidence_url = (data.get("evidence_url") or "").strip()
            activity.description  = (data.get("description") or "").strip() or None
            activity.reported_at  = now
            activity.score        = 5 if now.date() <= activity.delivery_date else 1

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
    def delete_activity(activity_id):
        activity = ActionPlanActivity.query.get(activity_id)
        if not activity:
            return False, {"activity": "Actividad no encontrada."}
        try:
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