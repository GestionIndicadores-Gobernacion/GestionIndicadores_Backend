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
        GET /kpis?year=YYYY[&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD]

        - Si llegan `date_from` y `date_to`, los reportes se filtran por
          ese rango (ignorando `year` para los reportes).
        - Si no, se filtra por `year` (default = año actual).
        """
        year = request.args.get("year", type=int) or datetime.utcnow().year
        date_from = request.args.get("date_from") or None
        date_to = request.args.get("date_to") or None
        snapshot = ReportKpiService.get_snapshot(year, date_from, date_to)
        return jsonify(snapshot), 200


@blp.route("/by-location")
class KpiByLocationResource(MethodView):

    @jwt_required()
    def get(self):
        """GET /kpis/by-location?year=YYYY[&date_from=&date_to=]"""
        year = request.args.get("year", type=int) or datetime.utcnow().year
        date_from = request.args.get("date_from") or None
        date_to = request.args.get("date_to") or None
        return jsonify(
            ReportKpiService.get_by_location(year, date_from, date_to)
        ), 200
