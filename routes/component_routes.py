from flask_smorest import Blueprint, abort
from flask.views import MethodView
from db import db
from models.component import Component
from schemas.component_schema import ComponentSchema

blp = Blueprint("Components", "components", description="Gestión de componentes")

@blp.route("/components")
class ComponentsList(MethodView):

    @blp.response(200, ComponentSchema(many=True))
    def get(self):
        return Component.query.all()

    @blp.arguments(ComponentSchema)
    @blp.response(201, ComponentSchema)
    def post(self, new_component):
        db.session.add(new_component)
        db.session.commit()
        return new_component
