from flask_smorest import Blueprint, abort
from flask.views import MethodView
from extensions import db

from models.component import Component
from schemas.component_schema import ComponentSchema

blp = Blueprint("Components", "components", description="Gestión de componentes")


@blp.route("/components")
class ComponentList(MethodView):

    @blp.response(200, ComponentSchema(many=True))
    def get(self):
        return Component.query.all()

    @blp.arguments(ComponentSchema)
    @blp.response(201, ComponentSchema)
    def post(self, new_component):

        # 🔥 Validar duplicado
        if Component.query.filter_by(name=new_component.name).first():
            abort(409, message="Ya existe un componente con este nombre.")

        db.session.add(new_component)
        db.session.commit()
        return new_component


@blp.route("/components/<int:id>")
class ComponentById(MethodView):

    @blp.response(200, ComponentSchema)
    def get(self, id):
        comp = Component.query.get(id)
        if not comp:
            abort(404, message="Componente no encontrado.")
        return comp

    @blp.arguments(ComponentSchema)
    @blp.response(200, ComponentSchema)
    def put(self, update_data, id):
        comp = Component.query.get(id)
        if not comp:
            abort(404, message="Componente no existe.")

        # 🔥 Validar duplicado solo si cambia el nombre
        if update_data.name != comp.name:
            exists = Component.query.filter_by(name=update_data.name).first()
            if exists:
                abort(409, message="Ya existe otro componente con este nombre.")

        # Actualizar campos
        comp.name = update_data.name
        comp.description = update_data.description
        comp.active = update_data.active if update_data.active is not None else comp.active

        db.session.commit()
        return comp

    def delete(self, id):
        comp = Component.query.get(id)
        if not comp:
            abort(404, message="Componente no existe.")
        db.session.delete(comp)
        db.session.commit()
        return {"message": "Componente eliminado correctamente."}
