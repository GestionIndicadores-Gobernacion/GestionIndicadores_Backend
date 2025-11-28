from os import abort
from flask_smorest import Blueprint
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from extensions import db
from models.component import Component
from models.strategy import Strategy
from schemas.strategy_schema import StrategySchema
from validators.strategy_validator import validate_strategy_payload

blp = Blueprint("strategy", "strategy", description="Gestión de estrategias")

@blp.route("/strategy")
class StrategyList(MethodView):

    @jwt_required()
    @blp.response(200, StrategySchema(many=True))
    def get(self):
        return Strategy.query.all()

    @jwt_required()
    @blp.arguments(StrategySchema)
    @blp.response(201, StrategySchema)
    def post(self, data):
        validate_strategy_payload(data)

        # data YA ES Strategy (SQLAlchemyAutoSchema lo crea)
        strategy = data

        db.session.add(strategy)
        db.session.commit()
        return strategy


@blp.route("/strategy/<int:id>")
class StrategyDetail(MethodView):

    @jwt_required()
    @blp.response(200, StrategySchema)
    def get(self, id):
        return Strategy.query.get_or_404(id)

    @jwt_required()
    @blp.arguments(StrategySchema)
    @blp.response(200, StrategySchema)
    def put(self, data, id):
        existing = Strategy.query.get_or_404(id)

        validate_strategy_payload(data)

        # data YA ES Strategy → copiamos atributos
        for key, value in data.__dict__.items():
            if key not in ["id", "_sa_instance_state"]:
                setattr(existing, key, value)

        db.session.commit()
        return existing

    @jwt_required()
    def delete(self, id):
        strategy = Strategy.query.get_or_404(id)
        db.session.delete(strategy)
        db.session.commit()
        return {"message": "Estrategia eliminada correctamente"}


@blp.route("/<int:strategy_id>/components")
class StrategyComponents(MethodView):

    @blp.response(200)
    def get(self, strategy_id):
        strategy = Strategy.query.get(strategy_id)
        if not strategy:
            abort(404, message="La estrategia no existe.")

        return strategy.components

@blp.route("/<int:component_id>/indicators")
class ComponentIndicators(MethodView):

    @blp.response(200)
    def get(self, component_id):
        comp = Component.query.get(component_id)
        if not comp:
            abort(404, message="El componente no existe.")

        return comp.indicators
