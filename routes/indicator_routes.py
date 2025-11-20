from flask_smorest import Blueprint, abort
from flask.views import MethodView
from extensions import db

from models.indicator import Indicator
from schemas.indicator_schema import IndicatorSchema

blp = Blueprint("Indicators", "indicators", description="Gestión de indicadores")


@blp.route("/indicators")
class IndicatorList(MethodView):

    @blp.response(200, IndicatorSchema(many=True))
    def get(self):
        return Indicator.query.all()

    @blp.arguments(IndicatorSchema)
    @blp.response(201, IndicatorSchema)
    def post(self, new_indicator):

        # ------------------------------
        # VALIDACIONES DE COHERENCIA
        # ------------------------------

        # use_list → allowed_values obligatorio
        if new_indicator.use_list and not new_indicator.allowed_values:
            abort(400, message="Debe enviar allowed_values cuando use_list es true.")

        # use_list=False → allowed_values debe ser None
        if not new_indicator.use_list and new_indicator.allowed_values:
            abort(400, message="allowed_values debe ser null cuando use_list es false.")

        # Unicidad por componente
        duplicate = Indicator.query.filter_by(
            name=new_indicator.name,
            component_id=new_indicator.component_id
        ).first()

        if duplicate:
            abort(409, message="Ya existe un indicador con ese nombre dentro de este componente.")

        db.session.add(new_indicator)
        db.session.commit()
        return new_indicator


@blp.route("/indicators/<int:id>")
class IndicatorById(MethodView):

    @blp.response(200, IndicatorSchema)
    def get(self, id):
        indicator = Indicator.query.get(id)
        if not indicator:
            abort(404, message="Indicador no encontrado.")
        return indicator

    @blp.arguments(IndicatorSchema)
    @blp.response(200, IndicatorSchema)
    def put(self, data, id):
        indicator = Indicator.query.get(id)
        if not indicator:
            abort(404, message="Indicador no existe.")

        # ---------------------------
        # VALIDACIONES DE COHERENCIA
        # ---------------------------

        if not data.use_list and data.allowed_values:
            abort(400, message="allowed_values debe ser null si use_list es false.")

        if data.use_list and not data.allowed_values:
            abort(400, message="Debe enviar allowed_values cuando use_list es true.")

        # Si cambia nombre o componente → validar duplicado
        if (data.name != indicator.name) or (data.component_id != indicator.component_id):

            duplicate = Indicator.query.filter_by(
                name=data.name,
                component_id=data.component_id
            ).first()

            if duplicate:
                abort(409, message="Ya existe un indicador con ese nombre en ese componente.")

        # ---------------------------
        # ACTUALIZAR CAMPOS
        # ---------------------------
        indicator.name = data.name
        indicator.description = data.description
        indicator.data_type = data.data_type
        indicator.required = data.required
        indicator.use_list = data.use_list
        indicator.allowed_values = data.allowed_values
        indicator.active = data.active
        indicator.component_id = data.component_id

        db.session.commit()
        return indicator

    def delete(self, id):
        indicator = Indicator.query.get(id)
        if not indicator:
            abort(404, message="Indicador no existe.")
        db.session.delete(indicator)
        db.session.commit()
        return {"message": "Indicador eliminado."}
