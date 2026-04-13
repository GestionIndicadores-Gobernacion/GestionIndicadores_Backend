from flask import jsonify, request
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.modules.action_plans.schemas.action_plan_schema import (
    ActionPlanCreateSchema,
    ActionPlanActivityReportSchema,
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

        # Cargar planes con relaciones eager para evitar lazy loading fuera de sesión
        plans = ActionPlan.query.options(
            selectinload(ActionPlan.plan_objectives)
            .selectinload(ActionPlanObjective.activities)
            .selectinload(ActionPlanActivity.linked_report)
        ).all()

        grouped: dict[str, dict] = {}

        for plan in plans:
            responsible = (plan.responsible or "").strip()
            if not responsible:
                continue

            if responsible not in grouped:
                grouped[responsible] = {
                    "responsible": responsible,
                    "plans_owner": [],
                    "activities": [],
                }

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
                    if owner_info not in grouped[responsible]["plans_owner"]:
                        grouped[responsible]["plans_owner"].append(owner_info)

            for obj in plan.plan_objectives:
                for activity in obj.activities:
                    try:
                        c_score = activity.computed_score
                    except Exception:
                        c_score = activity.score or 0

                    grouped[responsible]["activities"].append({
                        "id":             activity.id,
                        "name":           activity.name,
                        "delivery_date":  str(activity.delivery_date),
                        "status":         activity.status,
                        "score":          activity.score,
                        "computed_score": c_score,
                        "reported_at":    str(activity.reported_at) if activity.reported_at else None,
                        "evidence_url":   activity.evidence_url,
                    })

        result = []
        for responsible, data in grouped.items():
            activities = data["activities"]   # ← definir PRIMERO

            completed = [a for a in activities if a["evidence_url"]]
            running   = [a for a in activities if not a["evidence_url"] and date.today() <= date.fromisoformat(a["delivery_date"])]
            overdue   = [a for a in activities if not a["evidence_url"] and date.today() > date.fromisoformat(a["delivery_date"])]

            total_score = sum(a["computed_score"] or 0 for a in activities)   # ← computed_score

            result.append({
                "responsible":      responsible,
                "plans_owner":      data["plans_owner"],
                "total_activities": len(activities),
                "completed":        len(completed),
                "running":          len(running),
                "pending":          len(overdue),
                "overdue":          len(overdue),
                "total_score":      total_score,
                "activities":       activities,
            })

        return jsonify(result), 200