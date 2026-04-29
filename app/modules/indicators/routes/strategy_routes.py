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

        def _extract_value(val, field_type: str) -> float:
            """Extrae el total numérico de un valor según su field_type.

            ALINEADO con accumulators.py/_process_* — el avance calculado
            aquí debe coincidir exactamente con la suma de by_month del explorador.

            number               → valor directo
            select               → 1.0 por reporte (by_month += 1)
            multi_select         → 1.0 por reporte si lista no vacía (by_month += 1)
            dataset_select       → 1.0 por reporte (by_month += 1)
            dataset_multi_select → 1.0 por reporte si lista no vacía (by_month += 1)
            sum_group            → suma valores del dict
            grouped_data         → suma valores numéricos (plano o un nivel anidado)
            categorized_group    → suma data→cat→grupo→metrica (sub_sections excluidas,
                                   igual que accumulators no las suma a by_month)
            text / date / file   → 0.0
            """
            # Booleans son subclase de int en Python — nunca son valores válidos aquí
            if isinstance(val, bool):
                return 0.0

            # ── number ───────────────────────────────────────────────────────
            if isinstance(val, (int, float)):
                # dataset_select almacena un record_id entero; contar como 1 reporte
                return 1.0 if field_type == 'dataset_select' else float(val)

            # ── select: string no vacío → 1 por reporte ──────────────────────
            if field_type == 'select':
                return 1.0 if isinstance(val, str) and val.strip() else 0.0

            # ── multi_select / dataset_multi_select: lista no vacía → 1 reporte
            # accumulators.py línea 74: acc["by_month"][month_key] += 1 (no por opción)
            if field_type in ('multi_select', 'dataset_multi_select'):
                return 1.0 if isinstance(val, list) and len(val) > 0 else 0.0

            if not isinstance(val, dict):
                return 0.0

            # ── sum_group: { "Niños": 7, "Niñas": 3 } → 10 ──────────────────
            if field_type == 'sum_group':
                return float(sum(
                    v for v in val.values()
                    if isinstance(v, (int, float)) and not isinstance(v, bool)
                ))

            # ── categorized_group: data→cat→grupo→metrica ────────────────────
            # sub_sections NO se suman al by_month en accumulators (solo a by_nested)
            if field_type == 'categorized_group':
                total = 0.0
                for cat_data in val.get('data', {}).values():
                    if not isinstance(cat_data, dict):
                        continue
                    for group_data in cat_data.values():
                        if not isinstance(group_data, dict):
                            continue
                        for v in group_data.values():
                            if isinstance(v, (int, float)) and not isinstance(v, bool):
                                total += v
                return total

            # ── grouped_data: { grupo: n } o { grupo: { sub: n } } ───────────
            if field_type == 'grouped_data':
                total = 0.0
                for group_val in val.values():
                    if isinstance(group_val, (int, float)) and not isinstance(group_val, bool):
                        total += group_val
                    elif isinstance(group_val, dict):
                        total += sum(
                            v for v in group_val.values()
                            if isinstance(v, (int, float)) and not isinstance(v, bool)
                        )
                return total

            return 0.0

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

        # indicator_id → field_type (para extraer valores correctamente)
        field_type_map = {ind.id: ind.field_type for ind in indicators}

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

        # Indexamos el avance por (component_id, indicator_id) — un mismo
        # indicator_id puede estar asociado a varios componentes (p.ej. el 96
        # "CANTIDAD DE PERSONAS ASISTIDAS" se reusa en Asistencias Técnicas,
        # Juntas Defensoras y Alianzas Académicas). Si solo agrupásemos por
        # indicator_id, los reportes de un componente contaminarían el avance
        # del otro.
        actual_by_pair: dict[tuple[int, int], float] = defaultdict(float)
        for report in reports:
            for iv in report.indicator_values:
                if iv.indicator_id in active_indicator_ids:
                    ft = field_type_map.get(iv.indicator_id, 'number')
                    actual_by_pair[(report.component_id, iv.indicator_id)] += \
                        _extract_value(iv.value, ft)

        # ── 6.b/6.c. Overrides desde Datasets ─────────────────────────────────
        # Helpers compartidos por todos los overrides que cruzan con un dataset.
        if active_indicator_ids & {76, 69}:
            import re as _re
            from app.modules.datasets.models.dataset import Dataset
            from app.modules.datasets.models.table import Table
            from app.modules.datasets.models.record import Record
            from sqlalchemy import func

            def _year_from_fecha(v) -> int | None:
                """Extrae el año de un valor 'fecha' guardado en el JSON.

                Soporta:
                  - ISO 'YYYY-MM-DD[ THH:MM:SS]'  ← Timestamp.isoformat().
                  - 'DD/MM/YYYY' o 'D/M/YYYY'.
                  - 'YYYY/MM/DD'.
                  - Cualquier 20XX suelto (sirve para textos como
                    "22 julio de 2025").
                """
                if v is None or v == "":
                    return None
                s = str(v).strip()
                m = _re.match(r'^(\d{4})-\d{1,2}-\d{1,2}', s)
                if m: return int(m.group(1))
                m = _re.match(r'^\d{1,2}/\d{1,2}/(\d{4})\b', s)
                if m: return int(m.group(1))
                m = _re.match(r'^(\d{4})/\d{1,2}/\d{1,2}', s)
                if m: return int(m.group(1))
                m = _re.search(r'\b(20\d{2})\b', s)
                if m: return int(m.group(1))
                return None

            def _to_float(v) -> float:
                if v is None or v == "":
                    return 0.0
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return 0.0

            def _dataset_active_table(dataset_name_upper: str):
                ds = (
                    Dataset.query
                    .filter(func.upper(Dataset.name) == dataset_name_upper)
                    .first()
                )
                if not ds:
                    return None
                return Table.query.filter_by(dataset_id=ds.id, active=True).first()

            # ── 6.b. Indicador 76: NO DE PERSONAS CAPACITADAS (Promotores PYBA)
            # Fuente: dataset "PERSONAS CAPACITADAS CONSOLIDADO".
            # Avance: count de registros del dataset cuya `fecha` pertenezca
            # al año, SUMADO al avance que ya se haya recolectado desde
            # reportes manuales del módulo Reportes para ese mismo año.
            #
            # Por qué sumar y no sobrescribir: en 2025 el equipo reportaba
            # manualmente totales mensuales (suma ~3.500 en 16 reportes)
            # antes de que existiese el dataset; el dataset solo guarda 18
            # registros rezagados de 2025. Para 2026 ya no se reporta y
            # todo está en el dataset (456 registros). Si sobrescribimos,
            # 2025 muestra 18 cuando la realidad capturada es ~3.500.
            COMPONENT_PROMOTORES = 22
            if 76 in active_indicator_ids:
                count = 0
                table = _dataset_active_table("PERSONAS CAPACITADAS CONSOLIDADO")
                if table:
                    records = Record.query.filter_by(table_id=table.id).all()
                    count = sum(
                        1 for r in records
                        if r.data and _year_from_fecha(r.data.get("fecha")) == year
                    )
                actual_by_pair[(COMPONENT_PROMOTORES, 76)] += float(count)

            # ── 6.c. Indicador 69: CANTIDAD DE ALIMENTO ENTREGADO (Donatón)
            # Fuente: dataset "DONATON 2025".
            # Avance: suma de kg (alimento_perro + alimento_gato). Si ambos
            # están vacíos en una fila, usa la columna 'total' como fallback.
            # Filtra por data.fecha == year.
            COMPONENT_DONATON = 16
            if 69 in active_indicator_ids:
                kg_total = 0.0
                table = _dataset_active_table("DONATON 2025")
                if table:
                    records = Record.query.filter_by(table_id=table.id).all()
                    for r in records:
                        if not r.data:
                            continue
                        if _year_from_fecha(r.data.get("fecha")) != year:
                            continue
                        perro = _to_float(r.data.get("alimento_perro"))
                        gato  = _to_float(r.data.get("alimento_gato"))
                        if perro == 0.0 and gato == 0.0:
                            kg_total += _to_float(r.data.get("total"))
                        else:
                            kg_total += perro + gato
                # Suma al avance de reportes (mismo criterio que el ind. 76).
                actual_by_pair[(COMPONENT_DONATON, 69)] += kg_total

        # ── 7. Estrategias ────────────────────────────────────────────────────
        strat_ids = {c.strategy_id for c in components.values()}
        strategies = {s.id: s for s in Strategy.query.filter(Strategy.id.in_(strat_ids)).all()}

        # ── 8. Agrupar por componente ─────────────────────────────────────────
        indicators_by_comp: dict[int, list] = defaultdict(list)
        for ind in indicators:
            actual = round(actual_by_pair.get((ind.component_id, ind.id), 0.0), 2)
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