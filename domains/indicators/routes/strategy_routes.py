# domains/indicators/routes/strategy_routes.py
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity

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

def _is_admin():
    from domains.indicators.models.User.user import User
    user = User.query.get(get_jwt_identity())
    return user and user.role and user.role.name == "admin"


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
        
        if not _is_admin():
            abort(403, message="Sin permiso")  
        
        strategy, errors = StrategyHandler.create(data)
        if errors:
            return {"errors": errors}, 400
        return strategy


# ─── Rutas estáticas ANTES que las dinámicas /<int:id> ───────────────────────
from flask import request

@blp.route("/dashboard")
class StrategyDashboardResource(MethodView):

    @jwt_required()
    @blp.response(200, StrategyWithProgressSchema(many=True))
    def get(self):
        try:
            # año opcional — si no viene usa el año actual
            year = request.args.get('year', type=int)

            strategies = StrategyHandler.get_all()
            for s in strategies:
                s.progress = StrategyProgressService.get_progress(s, year=year)
            return strategies
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"message": str(e)}, 500

# ─── Rutas dinámicas ─────────────────────────────────────────────────────────

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
        
        if not _is_admin():
            abort(403, message="Sin permiso")  
        
        strategy = StrategyHandler.get_by_id(strategy_id)
        if not strategy:
            return {"message": "Strategy not found"}, 404
        return StrategyHandler.update(strategy, data)

    @jwt_required()
    @blp.response(204)
    def delete(self, strategy_id):
        
        if not _is_admin():
            abort(403, message="Sin permiso")  
        
        strategy = StrategyHandler.get_by_id(strategy_id)
        if not strategy:
            return {"message": "Strategy not found"}, 404
        StrategyHandler.delete(strategy)


@blp.route("/<int:strategy_id>/progress")
class StrategyProgressResource(MethodView):

    @jwt_required()
    @blp.response(200, StrategyWithProgressSchema)
    def get(self, strategy_id):
        strategy = StrategyHandler.get_by_id(strategy_id)
        if not strategy:
            return {"message": "Strategy not found"}, 404

        strategy.progress = StrategyProgressService.get_progress(strategy)
        return strategy