from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity

from domains.indicators.handlers.report_handler import ReportHandler
from domains.indicators.schemas.report_schema import ReportSchema
from domains.indicators.models.User.user import User


blp = Blueprint(
    "reports", "reports",
    url_prefix="/reports",
    description="Report management"
)


# =========================================================
# HELPERS
# =========================================================

def _current_user_id() -> int | None:
    """
    JWT devuelve string → DB usa int
    Evita comparaciones 5 != "5"
    """
    identity = get_jwt_identity()
    return int(identity) if identity is not None else None


def _is_admin() -> bool:
    user = User.query.get(_current_user_id())
    return user and user.role and user.role.name == "admin"


def _can_access(report) -> bool:
    """
    Permiso centralizado
    """
    if _is_admin():
        return True
    if report.user_id is None:
        return True
    return report.user_id == _current_user_id()


# =========================================================
# LIST + CREATE
# =========================================================

@blp.route("/")
class ReportList(MethodView):

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


# =========================================================
# DETAIL
# =========================================================

@blp.route("/<int:report_id>")
class ReportDetail(MethodView):

    @jwt_required()
    @blp.response(200, ReportSchema)
    def get(self, report_id):
        report = ReportHandler.get_by_id(report_id)
        if not report:
            abort(404, message="Report not found")

        if not _can_access(report):
            abort(403, message="No tienes permiso para ver este reporte")

        return report

    @jwt_required()
    @blp.arguments(ReportSchema)
    @blp.response(200, ReportSchema)
    def put(self, data, report_id):
        report = ReportHandler.get_by_id(report_id)
        if not report:
            abort(404, message="Report not found")

        if not _can_access(report):
            abort(403, message="No tienes permiso para editar este reporte")

        updated, errors = ReportHandler.update(report, data)
        if errors:
            abort(400, message=errors)
        return updated

    @jwt_required()
    @blp.response(204)
    def delete(self, report_id):
        report = ReportHandler.get_by_id(report_id)
        if not report:
            abort(404, message="Report not found")

        if not _can_access(report):
            abort(403, message="No tienes permiso para eliminar este reporte")

        ReportHandler.delete(report)


# =========================================================
# AGGREGATES
# =========================================================

@blp.route("/aggregate/component/<int:component_id>")
class ReportAggregateComponent(MethodView):

    @jwt_required()
    def get(self, component_id):
        return ReportHandler.aggregate_by_component(component_id)


@blp.route("/aggregate/strategy/<int:strategy_id>")
class ReportAggregateStrategy(MethodView):

    @jwt_required()
    def get(self, strategy_id):
        return ReportHandler.aggregate_by_strategy(strategy_id)
    
# =========================================================
# AGGREGATE POR INDICADOR
# =========================================================

@blp.route("/aggregate/component/<int:component_id>/indicators")
class ReportAggregateComponentIndicators(MethodView):

    @jwt_required()
    def get(self, component_id):
        return ReportHandler.aggregate_indicators_by_component(component_id)