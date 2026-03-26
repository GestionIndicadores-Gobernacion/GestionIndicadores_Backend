from flask import jsonify, request
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from domains.action_plans.schemas.action_plan_schema import (
    ActionPlanCreateSchema,
    ActionPlanActivityReportSchema,
    ActionPlanResponseSchema,
    ActionPlanActivitySchema,
    ActionPlanActivityDetailSchema,
)
from domains.action_plans.handlers.action_plan_handler import ActionPlanHandler

blp = Blueprint(
    "action_plans", __name__,
    url_prefix="/action-plans",
    description="Gestión de Planes de Acción"
)

def _get_current_user():
    from domains.indicators.models.User.user import User
    return User.query.get(get_jwt_identity())

def _can_manage_plans():
    from domains.indicators.models.User.user import User
    user = User.query.get(get_jwt_identity())
    return user and user.role and user.role.name in ("admin", "monitor")

def _is_viewer():
    user = _get_current_user()
    return user and user.role and user.role.name == "viewer"

def _can_edit_plan(plan):
    """Editor solo puede editar planes de sus componentes asignados."""
    user = _get_current_user()
    if not user:
        return False
    if user.role.name in ("admin", "monitor"):
        return True
    if user.role.name == "viewer":
        return False
    # editor — verificar componente asignado
    assigned = [uc.component_id for uc in user.component_assignments]
    return plan.component_id in assigned
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
        # Editor — verificar que el componente sea el suyo
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
        activity, errors = ActionPlanHandler.report_activity(activity_id, data)
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
        success, errors = ActionPlanHandler.delete_activity(activity_id)
        if not success:
            status_code = 404 if "activity" in errors else 422
            return jsonify({"errors": errors}), status_code
        return jsonify({"message": "Actividad eliminada"}), 200
    
@blp.route("/dashboard/users")
class ActionPlanUserDashboard(MethodView):

    @jwt_required()
    def get(self):
        from domains.indicators.models.User.user import User
        from domains.action_plans.models.action_plan import ActionPlanActivity, ActionPlanObjective, ActionPlan
        from datetime import date

        # Solo admin y monitor
        user = _get_current_user()
        if not user or user.role.name not in ("admin", "monitor"):
            return jsonify({"error": "Sin permiso"}), 403

        users = User.query.filter_by(is_active=True).all()
        result = []

        for u in users:
            # Todas las actividades donde este usuario es responsable del plan
            activities = (
                ActionPlanActivity.query
                .join(ActionPlanObjective)
                .join(ActionPlan)
                .filter(ActionPlan.user_id == u.id)
                .all()
            )

            if not activities:
                continue

            total       = len(activities)
            completed   = [a for a in activities if a.evidence_url]
            pending     = [a for a in activities if not a.evidence_url and date.today() <= a.delivery_date]
            overdue     = [a for a in activities if not a.evidence_url and date.today() > a.delivery_date]
            total_score = sum(a.score for a in completed if a.score)

            result.append({
                "user_id":    u.id,
                "first_name": u.first_name,
                "last_name":  u.last_name,
                "email":      u.email,
                "role":       u.role.name if u.role else None,
                "total_activities": total,
                "completed":  len(completed),
                "pending":    len(pending),
                "overdue":    len(overdue),
                "total_score": total_score,
                "activities": [
                    {
                        "id":            a.id,
                        "name":          a.name,
                        "delivery_date": str(a.delivery_date),
                        "status":        a.status,
                        "score":         a.score,
                        "reported_at":   str(a.reported_at) if a.reported_at else None,
                        "evidence_url":  a.evidence_url,
                    }
                    for a in activities
                ]
            })

        return jsonify(result), 200