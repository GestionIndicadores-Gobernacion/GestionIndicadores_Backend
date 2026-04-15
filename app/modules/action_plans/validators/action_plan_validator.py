from datetime import datetime, date, timedelta
from app.modules.indicators.models.Strategy.strategy import Strategy
from app.modules.indicators.models.Component.component import Component
from app.modules.indicators.models.Component.component_objective import ComponentObjective


class ActionPlanValidator:

    @staticmethod
    def validate_create(data):
        errors = {}

        strategy_id = data.get("strategy_id")
        if not strategy_id:
            errors["strategy_id"] = "La estrategia es requerida."
        else:
            if not Strategy.query.get(strategy_id):
                errors["strategy_id"] = "La estrategia no existe."

        component_id = data.get("component_id")
        if not component_id:
            errors["component_id"] = "El componente es requerido."
        else:
            component = Component.query.get(component_id)
            if not component:
                errors["component_id"] = "El componente no existe."
            elif strategy_id and not errors.get("strategy_id"):
                if component.strategy_id != strategy_id:
                    errors["component_id"] = "El componente no pertenece a la estrategia indicada."

        plan_objectives = data.get("plan_objectives")
        if not plan_objectives or not isinstance(plan_objectives, list) or len(plan_objectives) == 0:
            errors["plan_objectives"] = "Debe incluir al menos un objetivo."
        else:
            # Verificar que al menos uno tenga objective_id (del componente)
            has_component_objective = any(o.get("objective_id") for o in plan_objectives)
            if not has_component_objective:
                errors["plan_objectives"] = "Debe incluir al menos un objetivo del componente."
            else:
                obj_error = ActionPlanValidator._validate_objectives(plan_objectives, component_id)
                if obj_error:
                    errors["plan_objectives"] = obj_error

        return errors

    @staticmethod
    def validate_report(data, activity):
        errors = {}
        # Bloquear si la actividad ya fue reportada
        if activity.reported_at:
            errors["activity"] = "Esta actividad ya fue reportada."
            return errors
        # Validar evidence_url solo si fue proporcionado
        evidence_url = (data.get("evidence_url") or "").strip()
        if evidence_url and len(evidence_url) < 5:
            errors["evidence_url"] = "El link de evidencia no es válido."
        return errors

    @staticmethod
    def validate_add_evidence(data, activity, user_id, plan):
        """
        Valida que se pueda agregar o editar la evidencia de una actividad ya reportada.
        - La actividad debe haber sido reportada (reported_at seteado).
        - Solo dentro de los 8 días desde la fecha de entrega.
        - Solo el responsable de la actividad puede agregar/editar evidencia.
        """
        errors = {}

        if not activity.reported_at:
            errors["activity"] = "La actividad aún no ha sido reportada."
            return errors

        # Ventana de 8 días desde la fecha de entrega
        window_limit = activity.delivery_date + timedelta(days=8)
        if date.today() > window_limit:
            errors["activity"] = (
                "Ya no es posible agregar evidencia. "
                "El plazo de 8 días desde la fecha de entrega ha expirado."
            )
            return errors

        # Solo el responsable del plan puede agregar/editar evidencia
        responsible_ids = list(plan.responsible_user_ids)
        if activity.reported_by_user_id:
            responsible_ids.append(activity.reported_by_user_id)

        if int(user_id) not in responsible_ids:
            errors["activity"] = "Solo el responsable de la actividad puede agregar o editar la evidencia."
            return errors

        evidence_url = (data.get("evidence_url") or "").strip()
        if not evidence_url:
            errors["evidence_url"] = "El link de evidencia es requerido."
        elif len(evidence_url) < 5:
            errors["evidence_url"] = "El link de evidencia no es válido."
        return errors

    @staticmethod
    def _validate_objectives(objectives, component_id):
        for i, obj in enumerate(objectives):
            position = i + 1
            objective_id   = obj.get("objective_id")
            objective_text = (obj.get("objective_text", "") or "").strip()

            if objective_id:
                objective = ComponentObjective.query.get(objective_id)
                if not objective:
                    return f"El objetivo en posición {position} no existe."
                if component_id and objective.component_id != component_id:
                    return f"El objetivo en posición {position} no pertenece al componente."
            elif not objective_text:
                return f"El objetivo en posición {position} debe tener texto si no es del componente."

            activities = obj.get("activities", [])
            if not activities or len(activities) == 0:
                return f"El objetivo en posición {position} debe tener al menos una actividad."

            act_error = ActionPlanValidator._validate_activities(activities, position)
            if act_error:
                return act_error

        return None

    @staticmethod
    def _validate_activities(activities, obj_position):
        for i, act in enumerate(activities):
            name = act.get("name", "").strip()
            if not name:
                return f"Una actividad del objetivo {obj_position} no tiene nombre."
            if not act.get("deliverable", "").strip():
                return f"La actividad '{name}' no tiene entregable."
            delivery_date = act.get("delivery_date")
            if not delivery_date:
                return f"La actividad '{name}' no tiene fecha de entrega."
            if isinstance(delivery_date, str):
                try:
                    datetime.strptime(delivery_date, "%Y-%m-%d")
                except ValueError:
                    return f"La actividad '{name}' tiene formato de fecha inválido."
            support_staff = act.get("support_staff", [])
            if support_staff:
                for j, staff in enumerate(support_staff):
                    if not staff.get("name", "").strip():
                        return f"Personal de apoyo en actividad '{name}', posición {j+1} no tiene nombre."
        return None