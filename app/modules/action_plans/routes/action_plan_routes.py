from flask import jsonify, request
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.modules.action_plans.schemas.action_plan_schema import (
    ActionPlanCreateSchema,
    ActionPlanActivityReportSchema,
    ActionPlanActivityAddEvidenceSchema,
    ActionPlanActivityEditSchema,
    ActionPlanResponseSchema,
    ActionPlanActivitySchema,
    ActionPlanActivityDetailSchema,
)
from app.modules.action_plans.services.action_plan_handler import ActionPlanHandler

blp = Blueprint(
    "action_plans", __name__,
    url_prefix="/action-plans",
    description="Gestión de Planes de Acción"
)


def _get_current_user():
    from app.shared.models.user import User
    return User.query.get(get_jwt_identity())

def _can_manage_plans():
    user = _get_current_user()
    return user and user.role and user.role.name in ("admin", "monitor")

def _is_viewer():
    user = _get_current_user()
    return user and user.role and user.role.name == "viewer"

def _can_edit_plan(plan):
    user = _get_current_user()
    if not user:
        return False
    if user.role.name in ("admin", "monitor"):
        return True
    if user.role.name == "viewer":
        return False
    assigned = [uc.component_id for uc in user.component_assignments]
    return plan.component_id in assigned

def _get_activity_plan(activity_id: int):
    """Retorna (activity, plan) o (None, None) si no existe."""
    from app.modules.action_plans.models.action_plan import (
        ActionPlanActivity, ActionPlanObjective, ActionPlan
    )
    activity = ActionPlanActivity.query.get(activity_id)
    if not activity:
        return None, None
    plan = ActionPlan.query.get(activity.plan_objective.action_plan_id)
    return activity, plan


def _can_add_evidence(activity, plan) -> bool:
    """
    Solo el responsable del plan o quien reportó la actividad puede
    agregar/editar evidencia. Admin y monitor siempre pueden.
    """
    user = _get_current_user()
    if not user:
        return False
    if user.role.name in ("admin", "monitor"):
        return True
    if user.role.name == "viewer":
        return False
    if user.role.name == "editor":
        # Debe ser uno de los responsables del plan o quien reportó la actividad
        responsible_ids = list(plan.responsible_user_ids)
        if activity.reported_by_user_id:
            responsible_ids.append(activity.reported_by_user_id)
        return user.id in responsible_ids
    return False


def _can_interact_with_activity(activity, plan) -> bool:
    """
    Editor → puede si el plan es de su componente O si es el responsable del plan.
    Admin/Monitor → siempre puede.
    Viewer → nunca puede modificar.
    """
    user = _get_current_user()
    if not user:
        return False
    if user.role.name in ("admin", "monitor"):
        return True
    if user.role.name == "viewer":
        return False
    if user.role.name == "editor":
        assigned = [uc.component_id for uc in user.component_assignments]
        if plan.component_id in assigned:
            return True
        # También puede si es el responsable del plan
        if plan.responsible_user_id and plan.responsible_user_id == user.id:
            return True
        return False
    return False

@blp.route("/")
class ActionPlanList(MethodView):

    @blp.response(200, ActionPlanResponseSchema(many=True))
    @jwt_required()
    def get(self):
        return ActionPlanHandler.get_all(
            strategy_id=request.args.get("strategy_id", type=int),
            component_id=request.args.get("component_id", type=int),
            month=request.args.get("month", type=int),
            year=request.args.get("year", type=int),
        )

    @blp.arguments(ActionPlanCreateSchema)
    @blp.response(201, ActionPlanResponseSchema)
    @jwt_required()
    def post(self, data):
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403

        user = _get_current_user()
        if user.role.name == "editor":
            assigned = [uc.component_id for uc in user.component_assignments]
            if data.get("component_id") not in assigned:
                return jsonify({"error": "No puedes crear planes en este componente"}), 403

        plan, errors = ActionPlanHandler.create(data)
        if errors:
            return jsonify({"errors": errors}), 422
        return plan


@blp.route("/<int:plan_id>")
class ActionPlanDetail(MethodView):

    @blp.response(200, ActionPlanResponseSchema)
    @jwt_required()
    def get(self, plan_id):
        plan = ActionPlanHandler.get_by_id(plan_id)
        if not plan:
            return jsonify({"error": "No encontrado"}), 404
        return plan

    @jwt_required()
    def put(self, plan_id):          # ← NUEVO
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403
        plan = ActionPlanHandler.get_by_id(plan_id)
        if not plan:
            return jsonify({"error": "No encontrado"}), 404
        if not _can_edit_plan(plan):
            return jsonify({"error": "Sin permiso"}), 403
        data = request.get_json()
        updated_plan, errors = ActionPlanHandler.update_plan(plan_id, data)
        if errors:
            return jsonify({"errors": errors}), 422
        from app.modules.action_plans.schemas.action_plan_schema import ActionPlanResponseSchema
        return jsonify(ActionPlanResponseSchema().dump(updated_plan)), 200

    @jwt_required()
    def delete(self, plan_id):
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403
        plan = ActionPlanHandler.get_by_id(plan_id)
        if not plan:
            return jsonify({"error": "No encontrado"}), 404
        if not _can_edit_plan(plan):
            return jsonify({"error": "Sin permiso"}), 403
        success, errors = ActionPlanHandler.delete(plan_id)
        if not success:
            return jsonify({"errors": errors}), 404
        return jsonify({"message": "Eliminado"}), 200


@blp.route("/activities/<int:activity_id>/report")
class ActionPlanActivityReport(MethodView):

    @blp.arguments(ActionPlanActivityReportSchema)
    @jwt_required()
    def put(self, data, activity_id):
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403

        activity, plan = _get_activity_plan(activity_id)
        if not activity:
            return jsonify({"errors": {"activity": "Actividad no encontrada."}}), 404

        if not _can_interact_with_activity(activity, plan):
            return jsonify({"error": "Sin permiso para reportar esta actividad"}), 403

        activity, errors = ActionPlanHandler.report_activity(activity_id, data)
        if errors:
            status_code = 404 if "activity" in errors else 422
            return jsonify({"errors": errors}), status_code
        return jsonify(ActionPlanActivityDetailSchema().dump(activity)), 200


@blp.route("/activities/<int:activity_id>/edit")
class ActionPlanActivityEdit(MethodView):

    @blp.arguments(ActionPlanActivityEditSchema)
    @jwt_required()
    def put(self, data, activity_id):
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403

        activity, plan = _get_activity_plan(activity_id)
        if not activity:
            return jsonify({"errors": {"activity": "Actividad no encontrada."}}), 404

        if not _can_interact_with_activity(activity, plan):
            return jsonify({"error": "Sin permiso para editar esta actividad"}), 403

        edit_all = data.pop("edit_all", False)
        activity, errors = ActionPlanHandler.update_activity(activity_id, data, edit_all=edit_all)
        if errors:
            status_code = 404 if "activity" in errors else 422
            return jsonify({"errors": errors}), status_code
        return jsonify(ActionPlanActivityDetailSchema().dump(activity)), 200

@blp.route("/activities/<int:activity_id>")
class ActionPlanActivityDetail(MethodView):

    @jwt_required()
    def delete(self, activity_id):
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403

        activity, plan = _get_activity_plan(activity_id)
        if not activity:
            return jsonify({"errors": {"activity": "Actividad no encontrada."}}), 404

        if not _can_interact_with_activity(activity, plan):
            return jsonify({"error": "Sin permiso para eliminar esta actividad"}), 403

        delete_all = request.args.get("delete_all", "false").lower() == "true"
        success, errors = ActionPlanHandler.delete_activity(activity_id, delete_all=delete_all)
        if not success:
            status_code = 404 if "activity" in errors else 422
            return jsonify({"errors": errors}), status_code
        return jsonify({"message": "Actividad eliminada"}), 200

@blp.route("/activities/<int:activity_id>/evidence")
class ActionPlanActivityEvidence(MethodView):
    """
    Agrega o edita la evidencia de una actividad ya reportada.
    Solo dentro de 8 días desde la fecha de entrega y solo el responsable.
    """

    @blp.arguments(ActionPlanActivityAddEvidenceSchema)
    @jwt_required()
    def put(self, data, activity_id):
        if _is_viewer():
            return jsonify({"error": "Sin permiso"}), 403

        activity, plan = _get_activity_plan(activity_id)
        if not activity:
            return jsonify({"errors": {"activity": "Actividad no encontrada."}}), 404

        if not _can_add_evidence(activity, plan):
            return jsonify({"error": "Solo el responsable de la actividad puede agregar o editar la evidencia."}), 403

        activity, errors = ActionPlanHandler.add_evidence(activity_id, data)
        if errors:
            status_code = 404 if "activity" in errors else 422
            return jsonify({"errors": errors}), status_code
        return jsonify(ActionPlanActivityDetailSchema().dump(activity)), 200


@blp.route("/dashboard/users")
class ActionPlanUserDashboard(MethodView):

    @jwt_required()
    def get(self):
        from app.modules.action_plans.models.action_plan import ActionPlanActivity, ActionPlanObjective, ActionPlan
        from app.shared.models.user import User
        from sqlalchemy.orm import selectinload
        from datetime import date

        user = _get_current_user()
        if not user or user.role.name not in ("admin", "monitor"):
            return jsonify({"error": "Sin permiso"}), 403

        from app.modules.action_plans.models.action_plan import ActionPlanResponsibleUser
        from sqlalchemy.orm import selectinload as sil

        # Cargar planes con relaciones eager para evitar lazy loading fuera de sesión
        plans = ActionPlan.query.options(
            selectinload(ActionPlan.plan_objectives)
            .selectinload(ActionPlanObjective.activities)
            .selectinload(ActionPlanActivity.linked_report),
            selectinload(ActionPlan.responsible_users)
        ).all()

        grouped: dict[str, dict] = {}

        def _get_or_create_group(key: str, display_name: str):
            if key not in grouped:
                grouped[key] = {
                    "responsible": display_name,
                    "plans_owner": [],
                    "activities": [],
                }
            return grouped[key]

        for plan in plans:
            # Determinar lista de responsables para agrupar
            plan_responsible_entries = []

            # Sistema nuevo: múltiples responsables
            if plan.responsible_users:
                for ru in plan.responsible_users:
                    if ru.user:
                        name = f"{ru.user.first_name} {ru.user.last_name}".strip()
                        plan_responsible_entries.append((f"user_{ru.user_id}", name))
            # Fallback legacy: responsible_user_id
            elif plan.responsible_user_id:
                u = User.query.get(plan.responsible_user_id)
                if u:
                    name = f"{u.first_name} {u.last_name}".strip()
                    plan_responsible_entries.append((f"user_{u.id}", name))
            # Fallback texto libre
            elif plan.responsible:
                txt = plan.responsible.strip()
                if txt:
                    plan_responsible_entries.append((txt, txt))

            if not plan_responsible_entries:
                continue

            for group_key, display_name in plan_responsible_entries:
                grp = _get_or_create_group(group_key, display_name)

                if plan.user_id:
                    owner = User.query.get(plan.user_id)
                    if owner:
                        owner_info = {
                            "user_id":    owner.id,
                            "first_name": owner.first_name,
                            "last_name":  owner.last_name,
                            "email":      owner.email,
                            "role":       owner.role.name if owner.role else None,
                        }
                        if owner_info not in grp["plans_owner"]:
                            grp["plans_owner"].append(owner_info)

                for obj in plan.plan_objectives:
                    for activity in obj.activities:
                        try:
                            c_score = activity.computed_score
                        except Exception:
                            c_score = activity.score or 0

                        # Verificar si tiene reporte vinculado
                        has_linked_report = False
                        try:
                            has_linked_report = activity.linked_report is not None
                        except Exception:
                            pass

                        grp["activities"].append({
                            "id":                activity.id,
                            "name":              activity.name,
                            "delivery_date":     str(activity.delivery_date),
                            "status":            activity.status,
                            "score":             activity.score,
                            "computed_score":    c_score,
                            "reported_at":       str(activity.reported_at) if activity.reported_at else None,
                            "evidence_url":      activity.evidence_url,
                            "generates_report":  activity.generates_report,
                            "has_linked_report": has_linked_report,
                        })

        result = []
        for _key, data in grouped.items():
            activities = data["activities"]

            completed        = [a for a in activities if a["evidence_url"]]
            pending_evidence = [a for a in activities if a["reported_at"] and not a["evidence_url"]]
            running          = [a for a in activities if not a["reported_at"] and not a["evidence_url"] and date.today() <= date.fromisoformat(a["delivery_date"])]
            overdue          = [a for a in activities if not a["reported_at"] and not a["evidence_url"] and date.today() > date.fromisoformat(a["delivery_date"])]

            # Actividades que generan reporte pero no tienen reporte vinculado
            without_report = [
                a for a in activities
                if a["generates_report"] and not a["has_linked_report"]
            ]

            total_score = sum(a["computed_score"] or 0 for a in activities)

            result.append({
                "responsible":               data["responsible"],
                "plans_owner":               data["plans_owner"],
                "total_activities":          len(activities),
                "completed":                 len(completed),
                "pending_evidence":          len(pending_evidence),
                "running":                   len(running),
                "pending":                   len(overdue),
                "overdue":                   len(overdue),
                "total_score":               total_score,
                "activities_without_report": len(without_report),
                "activities":                activities,
            })

        return jsonify(result), 200