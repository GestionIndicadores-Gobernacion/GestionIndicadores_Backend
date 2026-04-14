# app/modules/indicators/routes/strategy_routes.py
from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.modules.indicators.services.strategy_handler import StrategyHandler
from app.modules.indicators.schemas.strategy_schema import StrategySchema
from app.modules.indicators.schemas.strategy_progress_schema import StrategyWithProgressSchema
from app.modules.indicators.services.strategy_progress_service import StrategyProgressService

blp = Blueprint(
    "strategies",
    "strategies",
    url_prefix="/strategies",
    description="Strategy management"
)

def _is_admin():
    from app.shared.models.user import User
    user = User.query.get(get_jwt_identity())
    return user and user.role and user.role.name == "admin"


@blp.route("/")
class StrategyListResource(MethodView):

    @jwt_required()
    @blp.response(200, StrategySchema(many=True))
    def get(self):
        return StrategyHandler.get_all()

    @jwt_required()
    @blp.arguments(StrategySchema)
    @blp.response(201, StrategySchema)
    def post(self, data):
        
        if not _is_admin():
            abort(403, message="Sin permiso")  
        
        strategy, errors = StrategyHandler.create(data)
        if errors:
            return {"errors": errors}, 400
        return strategy


# ─── Rutas estáticas ANTES que las dinámicas /<int:id> ───────────────────────
from flask import request, jsonify


@blp.route("/component-goals")
class ComponentGoalsResource(MethodView):
    """
    Devuelve el cumplimiento de cada componente por sus metas anuales de indicadores
    (ComponentIndicatorTarget). Agrupa por componente → lista de indicadores con
    meta, avance y porcentaje de cumplimiento para el año solicitado.
    """

    @jwt_required()
    def get(self):
        from datetime import datetime
        from collections import defaultdict
        from sqlalchemy import extract
        from sqlalchemy.orm import selectinload

        from app.modules.indicators.models.Strategy.strategy import Strategy
        from app.modules.indicators.models.Component.component import Component
        from app.modules.indicators.models.Component.component_indicator import ComponentIndicator
        from app.modules.indicators.models.Component.component_indicator_target import ComponentIndicatorTarget
        from app.modules.indicators.models.Report.report import Report
        from app.modules.indicators.models.Report.report_indicator_value import ReportIndicatorValue

        year               = request.args.get('year', type=int) or datetime.utcnow().year
        strategy_id_filter = request.args.get('strategy_id', type=int)

        # ── 1. Años disponibles (para el selector en el frontend) ────────────
        available_years = [
            row[0] for row in
            ComponentIndicatorTarget.query
            .with_entities(ComponentIndicatorTarget.year)
            .distinct()
            .order_by(ComponentIndicatorTarget.year.desc())
            .all()
        ]

        # ── 2. Targets del año seleccionado ──────────────────────────────────
        targets = ComponentIndicatorTarget.query.filter_by(year=year).all()

        if not targets:
            return jsonify({
                "year": year,
                "available_years": available_years,
                "unconfigured_count": 0,
                "items": [],
            }), 200

        # indicator_id → target_value
        target_map = {t.indicator_id: float(t.target_value) for t in targets}
        indicator_ids_with_target = set(target_map.keys())

        # ── 3. Indicadores con target ─────────────────────────────────────────
        indicators = ComponentIndicator.query.filter(
            ComponentIndicator.id.in_(indicator_ids_with_target)
        ).all()

        # ── 4. Componentes que tienen al menos un indicador con target ────────
        comp_ids_with_target = {ind.component_id for ind in indicators}

        comp_query = Component.query.filter(Component.id.in_(comp_ids_with_target))
        if strategy_id_filter:
            comp_query = comp_query.filter_by(strategy_id=strategy_id_filter)
        components = {c.id: c for c in comp_query.all()}

        # Filtrar indicadores al set de componentes válidos
        indicators = [ind for ind in indicators if ind.component_id in components]
        active_indicator_ids = {ind.id for ind in indicators}

        # ── 5. Contar componentes sin target en este año ──────────────────────
        all_comp_query = Component.query
        if strategy_id_filter:
            all_comp_query = all_comp_query.filter_by(strategy_id=strategy_id_filter)
        all_comp_ids = {c.id for c in all_comp_query.with_entities(Component.id).all()}
        unconfigured_count = len(all_comp_ids - comp_ids_with_target)

        # ── 6. Valores reales: sumar ReportIndicatorValue por indicator_id ────
        reports = (
            Report.query
            .filter(
                Report.component_id.in_(list(components.keys())),
                extract('year', Report.report_date) == year,
            )
            .options(selectinload(Report.indicator_values))
            .all()
        )

        actual_by_indicator: dict[int, float] = defaultdict(float)
        for report in reports:
            for iv in report.indicator_values:
                if iv.indicator_id in active_indicator_ids:
                    val = iv.value
                    if isinstance(val, (int, float)):
                        actual_by_indicator[iv.indicator_id] += float(val)

        # ── 7. Estrategias ────────────────────────────────────────────────────
        strat_ids = {c.strategy_id for c in components.values()}
        strategies = {s.id: s for s in Strategy.query.filter(Strategy.id.in_(strat_ids)).all()}

        # ── 8. Agrupar por componente ─────────────────────────────────────────
        indicators_by_comp: dict[int, list] = defaultdict(list)
        for ind in indicators:
            actual = round(actual_by_indicator.get(ind.id, 0.0), 2)
            goal   = target_map.get(ind.id, 0.0)
            pct    = round(actual / goal * 100, 1) if goal > 0 else 0.0
            indicators_by_comp[ind.component_id].append({
                "indicator_id":   ind.id,
                "indicator_name": ind.name,
                "goal":           goal,
                "actual":         actual,
                "percent":        min(pct, 100.0),
            })

        result = []
        for comp_id, comp in components.items():
            inds = sorted(indicators_by_comp.get(comp_id, []), key=lambda x: x["indicator_name"])
            if not inds:
                continue
            strategy = strategies.get(comp.strategy_id)
            avg_pct  = round(sum(i["percent"] for i in inds) / len(inds), 1)
            result.append({
                "component_id":   comp.id,
                "component_name": comp.name,
                "strategy_id":    comp.strategy_id,
                "strategy_name":  strategy.name if strategy else "",
                "year":           year,
                "avg_percent":    avg_pct,
                "indicators":     inds,
            })

        result.sort(key=lambda x: x["component_name"])

        return jsonify({
            "year":               year,
            "available_years":    available_years,
            "unconfigured_count": unconfigured_count,
            "items":              result,
        }), 200


@blp.route("/dashboard")
class StrategyDashboardResource(MethodView):

    @jwt_required()
    @blp.response(200, StrategyWithProgressSchema(many=True))
    def get(self):
        try:
            year      = request.args.get('year', type=int)
            date_from = request.args.get('date_from')   # YYYY-MM-DD, opcional
            date_to   = request.args.get('date_to')     # YYYY-MM-DD, opcional

            strategies = StrategyHandler.get_all()
            for s in strategies:
                s.progress = StrategyProgressService.get_progress(
                    s,
                    year=year,
                    date_from=date_from,
                    date_to=date_to,
                )
            return strategies
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"message": str(e)}, 500

# ─── Rutas dinámicas ─────────────────────────────────────────────────────────

@blp.route("/<int:strategy_id>")
class StrategyResource(MethodView):

    @jwt_required()
    @blp.response(200, StrategySchema)
    def get(self, strategy_id):
        strategy = StrategyHandler.get_by_id(strategy_id)
        if not strategy:
            return {"message": "Strategy not found"}, 404
        return strategy

    @jwt_required()
    @blp.arguments(StrategySchema)
    @blp.response(200, StrategySchema)
    def put(self, data, strategy_id):
        
        if not _is_admin():
            abort(403, message="Sin permiso")  
        
        strategy = StrategyHandler.get_by_id(strategy_id)
        if not strategy:
            return {"message": "Strategy not found"}, 404
        return StrategyHandler.update(strategy, data)

    @jwt_required()
    @blp.response(204)
    def delete(self, strategy_id):
        
        if not _is_admin():
            abort(403, message="Sin permiso")  
        
        strategy = StrategyHandler.get_by_id(strategy_id)
        if not strategy:
            return {"message": "Strategy not found"}, 404
        StrategyHandler.delete(strategy)


@blp.route("/<int:strategy_id>/progress")
class StrategyProgressResource(MethodView):

    @jwt_required()
    @blp.response(200, StrategyWithProgressSchema)
    def get(self, strategy_id):
        strategy = StrategyHandler.get_by_id(strategy_id)
        if not strategy:
            return {"message": "Strategy not found"}, 404

        strategy.progress = StrategyProgressService.get_progress(strategy)
        return strategy