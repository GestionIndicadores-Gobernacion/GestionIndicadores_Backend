from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required

from domains.indicators.handlers.strategy_handler import StrategyHandler
from domains.indicators.schemas.strategy_schema import StrategySchema

blp = Blueprint(
    "strategies",
    "strategies",
    url_prefix="/strategies",
    description="Strategy management"
)


@blp.route("/")
class StrategyListResource(MethodView):

    @jwt_required()
    @blp.response(200, StrategySchema(many=True))
    def get(self):
        return StrategyHandler.get_all()

    @jwt_required()
    @blp.arguments(StrategySchema)
    @blp.response(201, StrategySchema)
    def post(self, data):
        strategy, errors = StrategyHandler.create(data)
        if errors:
            return {"errors": errors}, 400
        return strategy


@blp.route("/<int:strategy_id>")
class StrategyResource(MethodView):

    @jwt_required()
    @blp.response(200, StrategySchema)
    def get(self, strategy_id):
        strategy = StrategyHandler.get_by_id(strategy_id)
        if not strategy:
            return {"message": "Strategy not found"}, 404
        return strategy

    @jwt_required()
    @blp.arguments(StrategySchema)
    @blp.response(200, StrategySchema)
    def put(self, data, strategy_id):
        strategy = StrategyHandler.get_by_id(strategy_id)
        if not strategy:
            return {"message": "Strategy not found"}, 404
        return StrategyHandler.update(strategy, data)

    @jwt_required()
    @blp.response(204)
    def delete(self, strategy_id):
        strategy = StrategyHandler.get_by_id(strategy_id)
        if not strategy:
            return {"message": "Strategy not found"}, 404
        StrategyHandler.delete(strategy)
