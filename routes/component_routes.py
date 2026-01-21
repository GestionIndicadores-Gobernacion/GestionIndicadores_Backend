from flask_smorest import Blueprint, abort
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from extensions import db
from models.component import Component
from schemas.component_schema import ComponentSchema
from validators.component_validator import validate_component_payload

blp = Blueprint("component", "component", description="Gestión de componentes")


@blp.route("/component")
class ComponentList(MethodView):

    @jwt_required()
    @blp.response(200, ComponentSchema(many=True))
    def get(self):
        return Component.query.all()

    @jwt_required()
    @blp.arguments(ComponentSchema)
    @blp.response(201, ComponentSchema)
    def post(self, data):
        validate_component_payload(data)
        component = data
        db.session.add(component)
        db.session.commit()
        return component


@blp.route("/component/<int:id>")
class ComponentDetail(MethodView):

    @jwt_required()
    @blp.response(200, ComponentSchema)
    def get(self, id):
        return Component.query.get_or_404(id)

    @jwt_required()
    @blp.arguments(ComponentSchema)
    @blp.response(200, ComponentSchema)
    def put(self, data, id):
        existing = Component.query.get_or_404(id)
        validate_component_payload(data, component_id=id)

        for key, value in data.__dict__.items():
            if key not in ["id", "_sa_instance_state"]:
                setattr(existing, key, value)

        db.session.commit()
        return existing

    @jwt_required()
    def delete(self, id):
        component = Component.query.get_or_404(id)

        if len(component.indicators) > 0:
            abort(
                400,
                message=f"No se puede eliminar. El componente tiene {len(component.indicators)} indicador(es) asociados."
            )

        db.session.delete(component)
        db.session.commit()
        return {"message": "Componente eliminado correctamente"}


@blp.route("/component/by_activity/<int:activity_id>")
class ComponentByActivity(MethodView):

    @jwt_required()
    @blp.response(200, ComponentSchema(many=True))
    def get(self, activity_id):
        return Component.query.filter_by(activity_id=activity_id).all()
