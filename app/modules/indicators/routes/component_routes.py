from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.modules.indicators.services.component_handler import ComponentHandler
from app.modules.indicators.schemas.component_schema import ComponentSchema

from flask_smorest import abort

blp = Blueprint(
    "components",
    "components",
    url_prefix="/components",
    description="Component management"
)

from app.utils.permissions import is_admin as _is_admin, dual_required  # noqa: E402
from app.shared.permissions import PERM_COMPONENTS_MANAGE  # noqa: E402

@blp.route("/summary")
class ComponentSummaryResource(MethodView):
    """
    Listado ultra-liviano: solo `id` y `name`.

    Reemplazo de `/components/` cuando el cliente solo necesita poblar
    un mapa id→name (reports-list, dashboard, etc.). Evita los lazy
    loads de `objectives`, `mga_activities`, `indicators(+targets)` y
    los selectin de `public_policies` / `user_assignments` que dispara
    `ComponentSchema` aunque no se usen.
    """

    @jwt_required()
    def get(self):
        from app.modules.indicators.models.Component.component import Component
        rows = (
            Component.query
            .with_entities(Component.id, Component.name)
            .order_by(Component.name)
            .all()
        )
        return jsonify([{"id": id_, "name": name} for id_, name in rows]), 200


@blp.route("/")
class ComponentListResource(MethodView):

    @jwt_required()
    @blp.response(200, ComponentSchema(many=True))
    def get(self):
        return ComponentHandler.get_all()

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_COMPONENTS_MANAGE,))
    @blp.arguments(ComponentSchema)
    @blp.response(201, ComponentSchema)
    def post(self, data):
        component, errors = ComponentHandler.create(data)

        if errors:
            return {"errors": errors}, 400

        return component


@blp.route("/<int:component_id>")
class ComponentResource(MethodView):

    @jwt_required()
    @blp.response(200, ComponentSchema)
    def get(self, component_id):
        component = ComponentHandler.get_by_id(component_id)
        if not component:
            return {"message": "Component not found"}, 404
        return component

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_COMPONENTS_MANAGE,))
    @blp.arguments(ComponentSchema)
    @blp.response(200, ComponentSchema)
    def put(self, data, component_id):
        component = ComponentHandler.get_by_id(component_id)
        if not component:
            return {"message": "Component not found"}, 404

        updated, errors = ComponentHandler.update(component, data)

        if errors:
            print("ERRORS UPDATE:", errors)  # ← AGREGAR
            return {"errors": errors}, 400

        return updated

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_COMPONENTS_MANAGE,))
    @blp.response(204)
    def delete(self, component_id):
        component = ComponentHandler.get_by_id(component_id)
        if not component:
            return {"message": "Component not found"}, 404

        ComponentHandler.delete(component)
        
    @blp.route("/by-strategy/<int:strategy_id>")
    class ComponentByStrategyResource(MethodView):

        @jwt_required()
        @blp.response(200, ComponentSchema(many=True))
        def get(self, strategy_id):
            return ComponentHandler.get_by_strategy(strategy_id)
