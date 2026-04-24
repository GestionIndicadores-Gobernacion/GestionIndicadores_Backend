from flask_jwt_extended import get_jwt_identity
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import uuid

from app.core.extensions import db
from app.modules.action_plans.models.action_plan import (
    ActionPlan, ActionPlanObjective, ActionPlanActivity, ActionPlanSupportStaff,
    ActionPlanResponsibleUser
)
from app.modules.action_plans.validators.action_plan_validator import ActionPlanValidator
from app.shared.models.audit_log import AuditLog
from sqlalchemy.orm import selectinload

from app.modules.notifications.services.notification_handler import NotificationHandler

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

            # Vincular múltiples responsables
            responsible_ids = data.get("responsible_user_ids") or []
            # Compatibilidad: si no viene responsible_user_ids pero sí responsible_user_id
            if not responsible_ids and data.get("responsible_user_id"):
                responsible_ids = [data["responsible_user_id"]]
            for uid in responsible_ids:
                db.session.add(ActionPlanResponsibleUser(
                    action_plan_id=plan.id,
                    user_id=uid
                ))

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
                                name        = (staff.get("name") or "").strip(),
                                user_id     = staff.get("user_id"),
                            ))

            db.session.add(AuditLog(
                user_id=user_id,
                entity="action_plan",
                entity_id=plan.id,
                action="created"
            ))

            # ── Notificar a todos los responsables ───────────────────────────
            from app.shared.models.user import User
            creator = User.query.get(user_id)
            creator_name = f"{creator.first_name} {creator.last_name}" if creator else "Un usuario"
            component_name = plan.component.name if plan.component else ""

            notify_ids = set()
            for ru in plan.responsible_users:
                if ru.user_id and ru.user_id != int(user_id):
                    notify_ids.add(ru.user_id)
            # Fallback legacy
            if not notify_ids and plan.responsible_user_id and plan.responsible_user_id != int(user_id):
                notify_ids.add(plan.responsible_user_id)

            for nid in notify_ids:
                NotificationHandler.create(
                    user_id=nid,
                    title="Nuevo plan de acción asignado",
                    message=f"{creator_name} te asignó un plan de acción en {component_name}.",
                    category="action_plan",
                    entity_id=plan.id,
                )

            # ── Notificar al personal de apoyo vinculado como usuario ────────
            support_user_ids = set()
            for obj in plan.plan_objectives:
                for act in obj.activities:
                    for staff in act.support_staff:
                        if staff.user_id and staff.user_id != int(user_id):
                            support_user_ids.add(staff.user_id)

            for nid in support_user_ids - notify_ids:
                NotificationHandler.create(
                    user_id=nid,
                    title="Asignado como personal de apoyo",
                    message=f"{creator_name} te incluyó como personal de apoyo en un plan de acción en {component_name}.",
                    category="action_plan",
                    entity_id=plan.id,
                )

            db.session.commit()
            
            return plan, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def base_query(strategy_id=None, component_id=None, month=None, year=None):
        """Query base sin .all() — útil para paginar antes de ejecutar."""
        query = ActionPlan.query.options(
            selectinload(ActionPlan.plan_objectives).selectinload(
                ActionPlanObjective.activities
            ).selectinload(
                ActionPlanActivity.linked_report
            )
        )

        if strategy_id:
            query = query.filter(ActionPlan.strategy_id == strategy_id)
        if component_id:
            query = query.filter(ActionPlan.component_id == component_id)

        if month and year:
            from app.modules.action_plans.models.action_plan import ActionPlanObjective as APO
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

        return query.order_by(ActionPlan.id.asc())

    @staticmethod
    def get_all(strategy_id=None, component_id=None, month=None, year=None):
        return ActionPlanHandler.base_query(
            strategy_id=strategy_id, component_id=component_id,
            month=month, year=year,
        ).all()

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

            evidence_url = (data.get("evidence_url") or "").strip() or None
            activity.evidence_url        = evidence_url
            activity.description         = (data.get("description") or "").strip() or None
            activity.reported_at         = now
            activity.reported_by_user_id = int(user_id)

            # Auto-vincular reporte si el evidence_url coincide con algún evidence_link
            if activity.evidence_url and activity.generates_report:
                try:
                    from app.modules.indicators.models.Report.report import Report
                    matching = Report.query.filter(
                        Report.evidence_link == activity.evidence_url,
                        Report.action_plan_activity_id.is_(None)
                    ).first()
                    if matching:
                        matching.action_plan_activity_id = activity.id
                except Exception:
                    pass  # No interrumpir el reporte si falla el auto-link

            plan_id = activity.plan_objective.action_plan_id
            detail = f"Actividad #{activity_id} reportada"
            if not activity.evidence_url:
                detail += " (sin evidencia — pendiente de evidencia)"
            db.session.add(AuditLog(
                user_id=user_id,
                entity="action_plan",
                entity_id=plan_id,
                action="updated",
                detail=detail
            ))

            db.session.commit()
            return activity, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}

    @staticmethod
    def add_evidence(activity_id, data):
        """
        Agrega o edita la evidencia de una actividad ya reportada.
        Solo válido dentro de los 8 días desde la fecha de entrega.
        Solo el responsable puede hacerlo (validado en el validator).
        """
        from app.modules.action_plans.models.action_plan import ActionPlanObjective, ActionPlan
        activity = ActionPlanActivity.query.get(activity_id)
        if not activity:
            return None, {"activity": "Actividad no encontrada."}

        user_id = get_jwt_identity()
        plan = ActionPlan.query.get(activity.plan_objective.action_plan_id)

        errors = ActionPlanValidator.validate_add_evidence(data, activity, user_id, plan)
        if errors:
            return None, errors

        try:
            evidence_url = data.get("evidence_url", "").strip()
            activity.evidence_url = evidence_url

            # Auto-vincular reporte si el evidence_url coincide con algún evidence_link
            if activity.evidence_url and activity.generates_report:
                try:
                    from app.modules.indicators.models.Report.report import Report
                    matching = Report.query.filter(
                        Report.evidence_link == activity.evidence_url,
                        Report.action_plan_activity_id.is_(None)
                    ).first()
                    if matching:
                        matching.action_plan_activity_id = activity.id
                except Exception:
                    pass

            plan_id = activity.plan_objective.action_plan_id
            db.session.add(AuditLog(
                user_id=user_id,
                entity="action_plan",
                entity_id=plan_id,
                action="updated",
                detail=f"Actividad #{activity_id} — evidencia agregada/editada"
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
                ).filter(ActionPlanActivity.reported_at.is_(None)).all()

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
                                name=(staff.get("name") or "").strip(),
                                user_id=staff.get("user_id"),
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
                            name=(staff.get("name") or "").strip(),
                            user_id=staff.get("user_id"),
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
                ).filter(ActionPlanActivity.reported_at.is_(None)).all()
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
            old_responsible_ids = set(plan.responsible_user_ids)

            # Actualizar responsable
            if "responsible" in data:
                plan.responsible = (data["responsible"] or "").strip() or None

            # Actualizar responsable usuario (legacy)
            if "responsible_user_id" in data:
                plan.responsible_user_id = data["responsible_user_id"]

            # Actualizar múltiples responsables
            if "responsible_user_ids" in data:
                new_ids = set(data["responsible_user_ids"] or [])
                # Eliminar los que ya no están
                for ru in list(plan.responsible_users):
                    if ru.user_id not in new_ids:
                        db.session.delete(ru)
                # Agregar los nuevos
                existing_ids = {ru.user_id for ru in plan.responsible_users}
                for uid in new_ids:
                    if uid not in existing_ids:
                        db.session.add(ActionPlanResponsibleUser(
                            action_plan_id=plan.id,
                            user_id=uid
                        ))
                db.session.flush()
            
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

                # Eliminar actividades no reportadas del objetivo
                for act in list(plan_obj.activities):
                    if not act.reported_at:
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
                            name=(staff.get("name") or "").strip(),
                            user_id=staff.get("user_id"),
                        ))

            db.session.add(AuditLog(
                user_id=user_id,
                entity="action_plan",
                entity_id=plan.id,
                action="updated",
                detail="Plan editado completo"
            ))
            
            # ── Notificar a nuevos responsables ──────────────────────────
            from app.shared.models.user import User
            creator = User.query.get(user_id)
            creator_name = f"{creator.first_name} {creator.last_name}" if creator else "Un usuario"
            component_name = plan.component.name if plan.component else ""

            new_responsible_ids = set(plan.responsible_user_ids)
            added_responsibles = new_responsible_ids - old_responsible_ids - {int(user_id)}

            for nid in added_responsibles:
                NotificationHandler.create(
                    user_id=nid,
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