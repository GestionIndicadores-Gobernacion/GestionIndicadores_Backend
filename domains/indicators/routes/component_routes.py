from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required

from domains.indicators.handlers.component_handler import ComponentHandler
from domains.indicators.schemas.component_schema import ComponentSchema

blp = Blueprint(
    "components",
    "components",
    url_prefix="/components",
    description="Component management"
)


@blp.route("/")
class ComponentListResource(MethodView):

    @jwt_required()
    @blp.response(200, ComponentSchema(many=True))
    def get(self):
        return ComponentHandler.get_all()

    @jwt_required()
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
    @blp.arguments(ComponentSchema)
    @blp.response(200, ComponentSchema)
    def put(self, data, component_id):
        component = ComponentHandler.get_by_id(component_id)
        if not component:
            return {"message": "Component not found"}, 404

        updated, errors = ComponentHandler.update(component, data)

        if errors:
            return {"errors": errors}, 400

        return updated

    @jwt_required()
    @blp.response(204)
    def delete(self, component_id):
        component = ComponentHandler.get_by_id(component_id)
        if not component:
            return {"message": "Component not found"}, 404

        ComponentHandler.delete(component)
