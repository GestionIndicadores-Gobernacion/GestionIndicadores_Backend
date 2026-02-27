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


def _is_admin():
    from domains.indicators.models.User.user import User
    user = User.query.get(get_jwt_identity())
    return user and user.role and user.role.name == "admin"


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
        if not _is_admin() and plan.user_id is not None and plan.user_id != get_jwt_identity():
            return jsonify({"error": "Sin permiso"}), 403
        return plan

    @jwt_required()
    def delete(self, plan_id):
        plan = ActionPlanHandler.get_by_id(plan_id)
        if not plan:
            return jsonify({"error": "No encontrado"}), 404
        if not _is_admin() and plan.user_id is not None and plan.user_id != get_jwt_identity():
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
        activity, errors = ActionPlanHandler.report_activity(activity_id, data)
        if errors:
            status_code = 404 if "activity" in errors else 422
            return jsonify({"errors": errors}), status_code
        return jsonify(ActionPlanActivityDetailSchema().dump(activity)), 200  

@blp.route("/activities/<int:activity_id>")
class ActionPlanActivityDetail(MethodView):

    @jwt_required()
    def delete(self, activity_id):
        success, errors = ActionPlanHandler.delete_activity(activity_id)
        if not success:
            status_code = 404 if "activity" in errors else 422
            return jsonify({"errors": errors}), status_code
        return jsonify({"message": "Actividad eliminada"}), 200