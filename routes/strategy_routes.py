from flask_smorest import abort, Blueprint
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from extensions import db
from models.component import Component
from models.strategy import Strategy
from schemas.strategy_schema import StrategySchema
from validators.strategy_validator import validate_strategy_payload

blp = Blueprint("strategy", "strategy", description="Gestión de estrategias")


# ============================================
# 📌 LISTA Y CREACIÓN DE ESTRATEGIAS
# ============================================
@blp.route("/strategy")
class StrategyList(MethodView):

    @jwt_required()
    @blp.response(200, StrategySchema(many=True))
    def get(self):
        return Strategy.query.all()

    @jwt_required()
    @blp.arguments(StrategySchema, location="json")   # ← EVITA VALIDAR DELETE
    @blp.response(201, StrategySchema)
    def post(self, data):
        validate_strategy_payload(data)

        strategy = data
        db.session.add(strategy)
        db.session.commit()

        return strategy



# ============================================
# 📌 OBTENER / EDITAR / ELIMINAR ESTRATEGÍA
# ============================================
@blp.route("/strategy/<int:id>")
class StrategyDetail(MethodView):

    @jwt_required()
    @blp.response(200, StrategySchema)
    def get(self, id):
        return Strategy.query.get_or_404(id)

    @jwt_required()
    @blp.arguments(StrategySchema, location="json")   # ← IMPORTANTE
    @blp.response(200, StrategySchema)
    def put(self, data, id):
        existing = Strategy.query.get_or_404(id)

        validate_strategy_payload(data)

        # Copiar atributos excepto campos internos
        for key, value in data.__dict__.items():
            if key not in ["id", "_sa_instance_state"]:
                setattr(existing, key, value)

        db.session.commit()
        return existing

    @jwt_required()
    def delete(self, id):
        strategy = Strategy.query.get_or_404(id)

        if len(strategy.components) > 0:
            abort(
                400,
                message=f"No se puede eliminar. La estrategia tiene {len(strategy.components)} componentes asociados."
            )

        db.session.delete(strategy)
        db.session.commit()
        return {"message": "Estrategia eliminada correctamente"}




# ============================================
# 📌 OBTENER COMPONENTES DE UNA ESTRATEGIA
# ============================================
@blp.route("/<int:strategy_id>/components")
class StrategyComponents(MethodView):

    @blp.response(200)
    def get(self, strategy_id):
        strategy = Strategy.query.get(strategy_id)
        if not strategy:
            abort(404, message="La estrategia no existe.")

        return strategy.components



# ============================================
# 📌 OBTENER INDICADORES DE UN COMPONENTE
# ============================================
@blp.route("/<int:component_id>/indicators")
class ComponentIndicators(MethodView):

    @blp.response(200)
    def get(self, component_id):
        comp = Component.query.get(component_id)
        if not comp:
            abort(404, message="El componente no existe.")

        return comp.indicators
