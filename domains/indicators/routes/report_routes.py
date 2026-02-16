from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required

from domains.indicators.handlers.report_handler import ReportHandler
from domains.indicators.schemas.report_schema import ReportSchema

from flask_smorest import abort

blp = Blueprint(
    "reports",
    "reports",
    url_prefix="/reports",
    description="Report management"
)

@blp.route("/")
class ReportListResource(MethodView):

    @jwt_required()
    @blp.response(200, ReportSchema(many=True))
    def get(self):
        return ReportHandler.get_all()

    @jwt_required()
    @blp.arguments(ReportSchema)
    @blp.response(201, ReportSchema)
    def post(self, data):
        report, errors = ReportHandler.create(data)

        if errors:
            abort(400, message=errors)

        return report

@blp.route("/<int:report_id>")
class ReportResource(MethodView):

    @jwt_required()
    @blp.response(200, ReportSchema)
    def get(self, report_id):
        report = ReportHandler.get_by_id(report_id)
        if not report:
            return {"message": "Report not found"}, 404
        return report

    @jwt_required()
    @blp.arguments(ReportSchema)
    @blp.response(200, ReportSchema)
    def put(self, data, report_id):

        report = ReportHandler.get_by_id(report_id)
        if not report:
            abort(404, message="Report not found")

        updated, errors = ReportHandler.update(report, data)

        if errors:
            abort(400, message=errors)

        return updated

    @jwt_required()
    @blp.response(204)
    def delete(self, report_id):
        report = ReportHandler.get_by_id(report_id)
        if not report:
            return {"message": "Report not found"}, 404
        ReportHandler.delete(report)

@blp.route("/aggregate/component/<int:component_id>")
class ReportAggregateComponentResource(MethodView):

    @jwt_required()
    def get(self, component_id):
        return ReportHandler.aggregate_by_component(component_id)


@blp.route("/aggregate/strategy/<int:strategy_id>")
class ReportAggregateStrategyResource(MethodView):

    @jwt_required()
    def get(self, strategy_id):
        return ReportHandler.aggregate_by_strategy(strategy_id)
