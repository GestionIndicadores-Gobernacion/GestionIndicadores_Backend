from flask_smorest import Blueprint
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from extensions import db
from models.indicator import Indicator
from schemas.indicator_schema import IndicatorSchema
from validators.indicator_validator import validate_indicator_payload

blp = Blueprint("indicator", "indicator", description="Gestión de indicadores")

@blp.route("/indicator")
class IndicatorList(MethodView):

    @jwt_required()
    @blp.response(200, IndicatorSchema(many=True))
    def get(self):
        return Indicator.query.all()

    @jwt_required()
    @blp.arguments(IndicatorSchema)
    @blp.response(201, IndicatorSchema)
    def post(self, data):
        validate_indicator_payload(data)
        indicator = data
        db.session.add(indicator)
        db.session.commit()
        return indicator


@blp.route("/indicator/<int:id>")
class IndicatorDetail(MethodView):

    @jwt_required()
    @blp.response(200, IndicatorSchema)
    def get(self, id):
        return Indicator.query.get_or_404(id)

    @jwt_required()
    @blp.arguments(IndicatorSchema)
    @blp.response(200, IndicatorSchema)
    def put(self, data, id):
        existing = Indicator.query.get_or_404(id)
        validate_indicator_payload(data, indicator_id=id)

        for key, value in data.__dict__.items():
            if key not in ["id", "_sa_instance_state"]:
                setattr(existing, key, value)

        db.session.commit()
        return existing

    @jwt_required()
    def delete(self, id):
        indicator = Indicator.query.get_or_404(id)
        db.session.delete(indicator)
        db.session.commit()
        return {"message": "Indicador eliminado correctamente"}
