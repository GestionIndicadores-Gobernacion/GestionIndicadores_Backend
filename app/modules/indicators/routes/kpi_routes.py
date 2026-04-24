"""
KPIs del dashboard — fuente canónica.

Este endpoint reemplaza la lógica paralela que vivía en el frontend
(`reports-kpi.service.ts`). El servicio devuelve los mismos 7 valores
que la UI ya conoce, por lo que no hace falta modificar cards ni layout.
"""

from datetime import datetime

from flask import jsonify, request
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required

from app.modules.indicators.services.report_kpi_service import ReportKpiService


blp = Blueprint(
    "kpis", "kpis",
    url_prefix="/kpis",
    description="KPIs agregados del dashboard",
)


@blp.route("/")
class KpiResource(MethodView):

    @jwt_required()
    def get(self):
        """
        GET /kpis?year=YYYY

        Si no se indica `year`, se usa el año calendario actual.
        Cualquier usuario autenticado puede consultar los KPIs (la
        granularidad es agregada por año; no expone datos por usuario).
        """
        year = request.args.get("year", type=int) or datetime.utcnow().year
        snapshot = ReportKpiService.get_snapshot(year)
        return jsonify(snapshot), 200


@blp.route("/by-location")
class KpiByLocationResource(MethodView):

    @jwt_required()
    def get(self):
        """GET /kpis/by-location?year=YYYY"""
        year = request.args.get("year", type=int) or datetime.utcnow().year
        return jsonify(ReportKpiService.get_by_location(year)), 200
