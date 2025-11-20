from flask_smorest import Blueprint, abort
from flask.views import MethodView
from db import db

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

    def delete(self, id):
        indicator = Indicator.query.get(id)
        if not indicator:
            abort(404, message="Indicador no existe.")
        db.session.delete(indicator)
        db.session.commit()
        return {"message": "Indicador eliminado."}
