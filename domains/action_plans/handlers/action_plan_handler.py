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

from domains.notifications.handlers.notification_handler import NotificationHandler

def _generate_dates(start_date: date, recurrence: dict) -> list[date]:
    frequency = recurrence.get("frequency")
    until_raw = recurrence.get("until")
    if not until_raw:
        return [start_date]

    # until puede llegar como date o como string
    if isinstance(until_raw, date):
        until = until_raw
    else:
        until = date.fromisoformat(str(until_raw))

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
            next_month = current + relativedelta(months=1)
            # day_of_month puede ser None → usar el día actual
            day = recurrence.get("day_of_month") or current.day
            try:
                current = next_month.replace(day=int(day))
            except ValueError:
                import calendar
                last_day = calendar.monthrange(next_month.year, next_month.month)[1]
                current = next_month.replace(day=last_day)
        elif frequency == "yearly":
            current = current + relativedelta(years=1)
        elif frequency == "custom":
            interval = recurrence.get("interval") or 7
            current = current + timedelta(days=int(interval))
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
                responsible_user_id = data.get("responsible_user_id"),
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
                        recurrence_to_save = dict(recurrence)
                        if isinstance(recurrence_to_save.get("until"), date):
                            recurrence_to_save["until"] = recurrence_to_save["until"].isoformat()
                        dates = _generate_dates(base_date, recurrence)
                        group_id = str(uuid.uuid4())
                    else:
                        recurrence_to_save = None
                        dates = [base_date]
                        group_id = None

                    for delivery_date in dates:
                        activity = ActionPlanActivity(
                            plan_objective_id        = plan_obj.id,
                            name                     = act_data["name"].strip(),
                            deliverable              = act_data["deliverable"].strip(),
                            delivery_date            = delivery_date,
                            lugar                    = act_data.get("lugar"),
                            requires_boss_assistance = act_data.get("requires_boss_assistance", False),
                            generates_report         = act_data.get("generates_report", False),
                            recurrence_group_id      = group_id,
                            recurrence_rule          = recurrence_to_save,
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

             # ── Notificar al responsable ─────────────────────────────────
            if plan.responsible_user_id and plan.responsible_user_id != int(user_id):
                from domains.indicators.models.User.user import User
                creator = User.query.get(user_id)
                creator_name = f"{creator.first_name} {creator.last_name}" if creator else "Un usuario"
                component_name = plan.component.name if plan.component else ""

                NotificationHandler.create(
                    user_id=plan.responsible_user_id,
                    title="Nuevo plan de acción asignado",
                    message=f"{creator_name} te asignó un plan de acción en {component_name}.",
                    category="action_plan",
                    entity_id=plan.id,
                )
                
            db.session.commit()
            
            return plan, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def get_all(strategy_id=None, component_id=None, month=None, year=None):
        query = ActionPlan.query.options(
            selectinload(ActionPlan.plan_objectives).selectinload(
                ActionPlanObjective.activities
            ).selectinload(
                ActionPlanActivity.linked_report  # ← cargar el reporte vinculado junto con la actividad
            )
        )
        
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
                    act.lugar = data.get("lugar", act.lugar)
                    act.generates_report = data.get("generates_report", act.generates_report)
                    
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
                activity.lugar = data.get("lugar", activity.lugar)
                activity.generates_report = data.get("generates_report", activity.generates_report)
                
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
        
    @staticmethod
    def update_plan(plan_id, data):
        plan = ActionPlanHandler.get_by_id(plan_id)
        if not plan:
            return None, {"plan": "Plan no encontrado."}

        try:
            user_id = get_jwt_identity()
            old_responsible_user_id = plan.responsible_user_id

            # Actualizar responsable
            if "responsible" in data:
                plan.responsible = (data["responsible"] or "").strip() or None
                
            # Actualizar responsable usuario
            if "responsible_user_id" in data:
                plan.responsible_user_id = data["responsible_user_id"]
            
            # Actualizar actividades NO realizadas por objetivo
            for obj_data in data.get("plan_objectives", []):
                obj_id = obj_data.get("objective_id")
                obj_text = obj_data.get("objective_text")

                # Buscar objetivo existente en el plan
                plan_obj = next(
                    (o for o in plan.plan_objectives
                    if (obj_id and o.objective_id == obj_id) or
                        (obj_text and o.objective_text == obj_text)),
                    None
                )

                if not plan_obj:
                    # Crear objetivo nuevo si no existe
                    plan_obj = ActionPlanObjective(
                        action_plan_id=plan.id,
                        objective_id=obj_id,
                        objective_text=(obj_text or "").strip() or None,
                    )
                    db.session.add(plan_obj)
                    db.session.flush()

                # Eliminar actividades no realizadas del objetivo
                for act in list(plan_obj.activities):
                    if not act.evidence_url:
                        db.session.delete(act)
                db.session.flush()

                # Recrear actividades
                for act_data in obj_data.get("activities", []):
                    activity = ActionPlanActivity(
                        plan_objective_id=plan_obj.id,
                        name=act_data["name"].strip(),
                        deliverable=act_data["deliverable"].strip(),
                        delivery_date=date.fromisoformat(act_data["delivery_date"]),
                        lugar=act_data.get("lugar"),
                        requires_boss_assistance=act_data.get("requires_boss_assistance", False),
                        generates_report         = act_data.get("generates_report", False),
                    )
                    db.session.add(activity)
                    db.session.flush()
                    for staff in act_data.get("support_staff", []):
                        db.session.add(ActionPlanSupportStaff(
                            activity_id=activity.id,
                            name=(staff.get("name") or "").strip()
                        ))

            db.session.add(AuditLog(
                user_id=user_id,
                entity="action_plan",
                entity_id=plan.id,
                action="updated",
                detail="Plan editado completo"
            ))
            
            # ── Notificar si cambió el responsable ───────────────────────
            new_responsible = plan.responsible_user_id
            if (new_responsible
                    and new_responsible != old_responsible_user_id
                    and new_responsible != int(user_id)):
                from domains.indicators.models.User.user import User
                creator = User.query.get(user_id)
                creator_name = f"{creator.first_name} {creator.last_name}" if creator else "Un usuario"
                component_name = plan.component.name if plan.component else ""

                NotificationHandler.create(
                    user_id=new_responsible,
                    title="Plan de acción reasignado",
                    message=f"{creator_name} te asignó un plan de acción en {component_name}.",
                    category="action_plan",
                    entity_id=plan.id,
                )

            db.session.commit()
            return plan, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}