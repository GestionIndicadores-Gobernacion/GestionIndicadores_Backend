from flask import jsonify, g
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.modules.indicators.models.Report.report import Report
from app.modules.indicators.schemas.report_schema import ReportSchema
from app.shared.models.user import User

from app.modules.indicators.services.report_handler import ReportHandler
from app.modules.indicators.services.report_aggregate_handler import ReportAggregateHandler
from app.modules.indicators.services.report_indicator_handler import ReportIndicatorHandler
from app.utils.pagination import get_pagination_params, paginate_query, envelope

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


def _current_user():
    """
    Carga el usuario actual una sola vez por request (cache en flask.g).
    Antes, cada _is_admin / _can_see_all / _is_viewer / _can_access disparaba
    su propio User.query.get() → 3-6 queries redundantes por request.
    """
    cached = getattr(g, "_cached_current_user", None)
    if cached is not None:
        return cached if cached is not False else None
    uid = _current_user_id()
    user = User.query.get(uid) if uid is not None else None
    g._cached_current_user = user if user is not None else False
    return user


def _role_name() -> str:
    user = _current_user()
    return user.role.name if user and user.role else ""


def _is_admin() -> bool:
    return _role_name() == "admin"


def _can_see_all() -> bool:
    return _role_name() in ("admin", "monitor")


def _is_viewer() -> bool:
    return _role_name() == "viewer"


def _can_access(report) -> bool:
    if _is_viewer():
        return True  # viewer puede VER cualquier reporte, pero no editar/eliminar

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
    def get(self):
        """
        GET /reports/[?limit=&offset=]

        - Sin parámetros → lista completa (retrocompatible).
        - Con `limit`/`offset` → envelope `{ items, total, limit, offset }`.
        """
        user = _current_user()
        user_id = user.id if user else None
        see_all = _can_see_all()

        component_ids = []
        if not see_all and user is not None:
            component_ids = [uc.component_id for uc in (user.component_assignments or [])]

        query = ReportHandler.base_query(
            user_id=user_id, is_admin=see_all, component_ids=component_ids
        )

        paginated, limit, offset = get_pagination_params()
        if not paginated:
            return jsonify(ReportSchema(many=True).dump(query.all())), 200

        items, total = paginate_query(query, limit, offset)
        return jsonify(
            envelope(ReportSchema(many=True).dump(items), total, limit, offset)
        ), 200

    @jwt_required()
    @blp.arguments(ReportSchema)
    @blp.response(201, ReportSchema)
    def post(self, data):
        if _is_viewer():
            abort(403, message="No tienes permiso para crear reportes")

        # ← NUEVO: validar componente para editor
        user = _current_user()
        if user and user.role and user.role.name == "editor":
            assigned = [uc.component_id for uc in user.component_assignments]
            if data.get("component_id") not in assigned:
                abort(403, message="No puedes crear reportes en este componente")

        report, errors = ReportHandler.create(data)
        if errors:
            abort(400, message=errors)
        return report

@blp.route("/all")
class ReportListAll(MethodView):

    @jwt_required()
    @blp.response(200, ReportSchema(many=True))
    def get(self):
        # Lectura global usada por el dashboard para gráficas agregadas.
        # Abierto a todos los roles autenticados: el dashboard es el único
        # consumidor "público" y las restricciones de creación/edición/borrado
        # viven en los endpoints individuales (POST/PUT/DELETE de /reports).
        # El acceso al listado UI individual ya está restringido por
        # viewerGuard en el frontend.
        return ReportHandler.get_all(is_admin=True)
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
        
        if _is_viewer():
            abort(403, message="No tienes permiso para editar reportes")
        
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
        
        if _is_viewer():
            abort(403, message="No tienes permiso para editar reportes")
        
        report = ReportHandler.get_by_id(report_id)
        if not report:
            abort(404, message="Report not found")

        if not _can_access(report):
            abort(403, message="No tienes permiso para eliminar este reporte")

        ReportHandler.delete(report)
        
@blp.route("/<int:report_id>/link-activity/<int:activity_id>")
class ReportLinkActivity(MethodView):

    @jwt_required()
    def post(self, report_id, activity_id):
        """Vincula una actividad del plan de acción a un reporte existente."""
        if _is_viewer():
            abort(403, message="No tienes permiso")

        report = ReportHandler.get_by_id(report_id)
        if not report:
            abort(404, message="Reporte no encontrado")

        if not _can_access(report):
            abort(403, message="No tienes permiso para modificar este reporte")

        result, errors = ReportHandler._link_activity_to_report(report, activity_id)
        if errors:
            abort(422, message=errors)

        return jsonify(ReportSchema().dump(result)), 200

@blp.route("/prefill/activity/<int:activity_id>")
class ReportPrefillFromActivity(MethodView):

    @jwt_required()
    def get(self, activity_id):
        """
        Devuelve los datos precargados para crear un reporte desde una actividad.
        Si ya existe un reporte vinculado, lo retorna también.
        """
        from app.modules.action_plans.models.action_plan import ActionPlanActivity

        activity = ActionPlanActivity.query.get(activity_id)
        if not activity:
            abort(404, message="Actividad no encontrada")

        plan_obj = activity.plan_objective
        plan     = plan_obj.action_plan

        # ¿Ya tiene reporte vinculado?
        existing_report = activity.linked_report
        # ¿Existe algún reporte con el mismo evidence_url?
        report_by_link = None
        if activity.evidence_url:
            report_by_link = Report.query.filter_by(
                evidence_link=activity.evidence_url
            ).first()

        return jsonify({
            "activity_id":   activity.id,
            "activity_name": activity.name,
            "generates_report": activity.generates_report,
            "prefill": {
                "strategy_id":    plan.strategy_id,
                "component_id":   plan.component_id,
                "evidence_link":  activity.evidence_url,
            },
            "linked_report": ReportSchema().dump(existing_report) if existing_report else None,
            "report_by_evidence_link": {
                "id": report_by_link.id,
                "created_at": str(report_by_link.created_at),
            } if report_by_link and report_by_link != existing_report else None,
        }), 200

# =========================================================
# AGGREGATES
# =========================================================
@blp.route("/aggregate/component/<int:component_id>")
class ReportAggregateComponent(MethodView):
    @jwt_required()
    def get(self, component_id):
        from flask import request
        year      = request.args.get('year', type=int)
        date_from = request.args.get('date_from')
        date_to   = request.args.get('date_to')
        return ReportAggregateHandler.aggregate_by_component(
            component_id,
            year=year,
            date_from=date_from,
            date_to=date_to
        )


@blp.route("/aggregate/strategy/<int:strategy_id>")
class ReportAggregateStrategy(MethodView):
    @jwt_required()
    def get(self, strategy_id):
        return ReportAggregateHandler.aggregate_by_strategy(strategy_id)

@blp.route("/aggregate/component/<int:component_id>/indicators")
class ReportAggregateComponentIndicators(MethodView):
    @jwt_required()
    def get(self, component_id):
        from flask import request
        year      = request.args.get('year', type=int)
        date_from = request.args.get('date_from')
        date_to   = request.args.get('date_to')
        return ReportIndicatorHandler.aggregate_indicators_by_component(
            component_id,
            year=year,
            date_from=date_from,
            date_to=date_to
        )