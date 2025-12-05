from flask_smorest import abort, Blueprint
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from extensions import db

from models.activity import Activity
from models.strategy import Strategy

from schemas.activity_schema import ActivitySchema
from validators.activity_validator import validate_activity_payload

blp = Blueprint("activity", "activity", description="Gestión de actividades")


# ===========================================
# 📌 LISTA Y CREACIÓN DE ACTIVIDADES
# ===========================================
@blp.route("/activity")
class ActivityList(MethodView):

    @jwt_required()
    @blp.response(200, ActivitySchema(many=True))
    def get(self):
        return Activity.query.all()

    @jwt_required()
    @blp.arguments(ActivitySchema, location="json")
    @blp.response(201, ActivitySchema)
    def post(self, data):
        validate_activity_payload(data)

        # validar existencia de strategy_id
        strategy = Strategy.query.get(data.strategy_id)
        if not strategy:
            abort(404, message="La estrategia no existe.")

        activity = data
        db.session.add(activity)
        db.session.commit()

        return activity


# ===========================================
# 📌 GET / PUT / DELETE ACTIVIDAD
# ===========================================
@blp.route("/activity/<int:id>")
class ActivityDetail(MethodView):

    @jwt_required()
    @blp.response(200, ActivitySchema)
    def get(self, id):
        return Activity.query.get_or_404(id)

    @jwt_required()
    @blp.arguments(ActivitySchema, location="json")
    @blp.response(200, ActivitySchema)
    def put(self, data, id):
        existing = Activity.query.get_or_404(id)

        validate_activity_payload(data)

        for key, value in data.__dict__.items():
            if key not in ["id", "_sa_instance_state"]:
                setattr(existing, key, value)

        db.session.commit()
        return existing

    @jwt_required()
    def delete(self, id):
        activity = Activity.query.get_or_404(id)

        db.session.delete(activity)
        db.session.commit()

        return {"message": "Actividad eliminada correctamente"}
