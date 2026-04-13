from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.modules.indicators.services.strategy_metric_handler import StrategyMetricHandler
from app.modules.indicators.schemas.strategy_metric_schema import StrategyMetricSchema


blp = Blueprint(
    "strategy_metrics",
    "strategy_metrics",
    url_prefix="/strategy-metrics",
    description="Strategy metrics management"
)

def _is_admin():
    from app.shared.models.user import User
    user = User.query.get(get_jwt_identity())
    return user and user.role and user.role.name == "admin"

@blp.route("/")
class StrategyMetricListResource(MethodView):

    @jwt_required()
    @blp.response(200, StrategyMetricSchema(many=True))
    def get(self):
        return StrategyMetricHandler.get_all()

    @jwt_required()
    @blp.arguments(StrategyMetricSchema)
    @blp.response(201, StrategyMetricSchema)
    def post(self, data):
        
        if not _is_admin():
            abort(403, message="Sin permiso")  

        metric, errors = StrategyMetricHandler.create(data)

        if errors:
            return {"errors": errors}, 400

        return metric


@blp.route("/<int:metric_id>")
class StrategyMetricResource(MethodView):

    @jwt_required()
    @blp.response(200, StrategyMetricSchema)
    def get(self, metric_id):

        metric = StrategyMetricHandler.get_by_id(metric_id)

        if not metric:
            return {"message": "Metric not found"}, 404

        return metric

    @jwt_required()
    @blp.arguments(StrategyMetricSchema)
    @blp.response(200, StrategyMetricSchema)
    def put(self, data, metric_id):
        
        if not _is_admin():
            abort(403, message="Sin permiso")

        metric = StrategyMetricHandler.get_by_id(metric_id)

        if not metric:
            return {"message": "Metric not found"}, 404

        return StrategyMetricHandler.update(metric, data)

    @jwt_required()
    @blp.response(204)
    def delete(self, metric_id):

        if not _is_admin():
            abort(403, message="Sin permiso")

        metric = StrategyMetricHandler.get_by_id(metric_id)

        if not metric:
            return {"message": "Metric not found"}, 404

        StrategyMetricHandler.delete(metric)