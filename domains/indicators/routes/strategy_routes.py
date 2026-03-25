# domains/indicators/routes/strategy_routes.py
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required

from domains.indicators.handlers.strategy_handler import StrategyHandler
from domains.indicators.schemas.strategy_schema import StrategySchema
from domains.indicators.schemas.strategy_progress_schema import StrategyWithProgressSchema
from domains.indicators.services.strategy_progress_service import StrategyProgressService

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


# ─── Dashboard ────────────────────────────────────────────────────────────────

@blp.route("/dashboard")
class StrategyDashboardResource(MethodView):
    """
    Devuelve todas las estrategias con su progreso calculado para el año actual.
    Usado por el dashboard en strategy-list.
    """

    @jwt_required()
    @blp.response(200, StrategyWithProgressSchema(many=True))
    def get(self):
        strategies = StrategyHandler.get_all()

        # Adjuntar el progreso como atributo dinámico por cada estrategia
        # (no se persiste, solo se serializa via StrategyWithProgressSchema)
        for s in strategies:
            s.progress = StrategyProgressService.get_progress(s)

        return strategies


@blp.route("/<int:strategy_id>/progress")
class StrategyProgressResource(MethodView):
    """
    Devuelve el progreso de una estrategia específica.
    """

    @jwt_required()
    @blp.response(200, StrategyWithProgressSchema)
    def get(self, strategy_id):
        strategy = StrategyHandler.get_by_id(strategy_id)
        if not strategy:
            return {"message": "Strategy not found"}, 404

        strategy.progress = StrategyProgressService.get_progress(strategy)
        return strategy