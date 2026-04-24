# app/modules/indicators/services/strategy_progress_service.py

import json
import re
from datetime import datetime, date

from app.modules.datasets.models.record import Record
from app.modules.indicators.models.Strategy.strategy import Strategy
from app.modules.indicators.models.Report.report import Report


class StrategyProgressService:

    @staticmethod
    def get_progress(
        strategy: Strategy,
        year: int = None,
        date_from: str = None,
        date_to: str = None,
    ) -> dict:
        current_year  = year or datetime.utcnow().year
        goal_for_year = StrategyProgressService._get_goal_for_year(strategy, current_year)
        actual        = StrategyProgressService._calculate_actual(
            strategy, current_year,
            date_from=date_from, date_to=date_to
        )

        percent = 0.0
        if goal_for_year and goal_for_year > 0:
            percent = round((actual / float(goal_for_year)) * 100, 2)

        return {
            "current_year":        current_year,
            "current_year_number": StrategyProgressService._get_year_number(strategy, current_year),
            "current_year_goal":   float(goal_for_year) if goal_for_year else 0.0,
            "current_year_actual": actual,
            "percent":             min(percent, 100.0),
        }

    # ─── Año lógico ───────────────────────────────────────────────────────────

    @staticmethod
    def _get_base_year(strategy: Strategy) -> int:
        return 2024

    @staticmethod
    def _get_year_number(strategy: Strategy, calendar_year: int):
        base_year = StrategyProgressService._get_base_year(strategy)
        number    = calendar_year - base_year + 1
        return number if number >= 1 else None

    @staticmethod
    def _get_goal_for_year(strategy: Strategy, calendar_year: int):
        year_number = StrategyProgressService._get_year_number(strategy, calendar_year)
        if year_number is None:
            return None
        goal = next(
            (g for g in strategy.annual_goals if g.year_number == year_number),
            None
        )
        return goal.value if goal else None

    # ─── Valor real acumulado ─────────────────────────────────────────────────

    @staticmethod
    def _calculate_actual(
        strategy: Strategy,
        current_year: int,
        date_from: str = None,
        date_to: str = None,
    ) -> float:
        total = 0.0
        for metric in strategy.metrics:
            total += StrategyProgressService._calculate_metric(
                metric, strategy, current_year,
                date_from=date_from, date_to=date_to
            )
        return total

    @staticmethod
    def _calculate_metric(
        metric,
        strategy: Strategy,
        current_year: int,
        date_from: str = None,
        date_to: str = None,
    ) -> float:
        t = metric.metric_type

        if metric.year is not None and metric.year != current_year:
            return 0.0

        if t == "report_count":
            return StrategyProgressService._report_count(
                metric, strategy, current_year, date_from, date_to
            )
        if t == "report_sum":
            return StrategyProgressService._report_sum(
                metric, strategy, current_year, date_from, date_to
            )
        if t == "report_sum_nested":
            return StrategyProgressService._report_sum_nested(
                metric, strategy, current_year, date_from, date_to
            )
        if t == "dataset_count":
            return StrategyProgressService._dataset_count(metric, current_year)
        if t == "dataset_sum":
            return StrategyProgressService._dataset_sum(metric, current_year)
        if t == "manual":
            return float(metric.manual_value or 0)

        return 0.0

    # ─── Helper compartido para filtrar reportes ──────────────────────────────

    @staticmethod
    def _filter_reports(
        query,
        current_year: int,
        date_from: str = None,
        date_to: str = None,
    ):
        """
        Si vienen date_from y date_to filtra por rango de fechas.
        Si no, filtra por año calendario.
        """
        if date_from and date_to:
            from_ = date.fromisoformat(date_from)
            to_   = date.fromisoformat(date_to)
            return [r for r in query.all()
                    if from_ <= _report_date(r) <= to_]
        else:
            return [r for r in query.all()
                    if _report_year(r) == current_year]

    # ─── Implementaciones por tipo ────────────────────────────────────────────

    @staticmethod
    def _report_count(
        metric,
        strategy: Strategy,
        current_year: int,
        date_from: str = None,
        date_to: str = None,
    ) -> float:
        query = Report.query.filter_by(strategy_id=strategy.id)
        if metric.component_id:
            query = query.filter_by(component_id=metric.component_id)

        reports = StrategyProgressService._filter_reports(
            query, current_year, date_from, date_to
        )
        return float(len(reports))

    @staticmethod
    def _report_sum(
        metric,
        strategy: Strategy,
        current_year: int,
        date_from: str = None,
        date_to: str = None,
    ) -> float:
        if not metric.field_name:
            return 0.0

        # field_name puede ser un ID único ("76"), una lista CSV
        # ("163,162,164") o un JSON array ("[163,162,164]").
        indicator_ids = _parse_indicator_ids(metric.field_name)
        if not indicator_ids:
            return 0.0

        query = Report.query.filter_by(strategy_id=strategy.id)
        if metric.component_id:
            query = query.filter_by(component_id=metric.component_id)

        reports = StrategyProgressService._filter_reports(
            query, current_year, date_from, date_to
        )

        target_ids = set(indicator_ids)
        total = 0.0
        for r in reports:
            for iv in (r.indicator_values or []):
                if iv.indicator_id not in target_ids or iv.value is None:
                    continue
                # Valor plano (int/float/decimal/string numérico)
                try:
                    total += float(iv.value)
                    continue
                except (ValueError, TypeError):
                    pass
                # Valor estructurado (dict/list): indicadores tipo
                # "sum_group" u otras estructuras JSON con números
                # anidados. Sumar todos los numéricos encontrados.
                total += _sum_any_numeric(iv.value)

        return total

    @staticmethod
    def _report_sum_nested(
        metric,
        strategy: Strategy,
        current_year: int,
        date_from: str = None,
        date_to: str = None,
    ) -> float:
        if not metric.field_name:
            return 0.0

        # Acepta un ID único, CSV o JSON array (igual que report_sum).
        indicator_ids = _parse_indicator_ids(metric.field_name)
        if not indicator_ids:
            return 0.0

        query = Report.query.filter_by(strategy_id=strategy.id)
        if metric.component_id:
            query = query.filter_by(component_id=metric.component_id)

        reports = StrategyProgressService._filter_reports(
            query, current_year, date_from, date_to
        )

        target_ids = set(indicator_ids)
        total = 0.0
        for r in reports:
            for iv in (r.indicator_values or []):
                if iv.indicator_id not in target_ids:
                    continue
                if not isinstance(iv.value, dict):
                    continue
                data = iv.value.get('data')
                if not data or not isinstance(data, dict):
                    continue
                total += _sum_nested_key(data, "no_de_animales_esterilizados")

        return total

    @staticmethod
    def _dataset_count(metric, current_year: int) -> float:
        if not metric.dataset_id:
            return 0.0

        from app.modules.datasets.models.table import Table
        table = Table.query.filter_by(
            dataset_id=metric.dataset_id,
            active=True
        ).first()

        if not table:
            return 0.0

        records = Record.query.filter_by(table_id=table.id).all()
        return float(sum(
            1 for r in records
            if r.data and r.data.get('mes') not in (None, '')
        ))

    @staticmethod
    def _dataset_sum(metric, current_year: int) -> float:
        if not metric.dataset_id or not metric.field_name:
            return 0.0

        from app.modules.datasets.models.table import Table
        table = Table.query.filter_by(
            dataset_id=metric.dataset_id,
            active=True
        ).first()

        if not table:
            return 0.0

        records = Record.query.filter_by(table_id=table.id).all()
        total = 0.0
        for r in records:
            if not r.data:
                continue
            val = r.data.get(metric.field_name)
            if val is not None:
                try:
                    total += float(val)
                except (ValueError, TypeError):
                    pass
        return total


# ─── Helpers privados ─────────────────────────────────────────────────────────

def _report_year(report) -> int:
    d = report.report_date
    if isinstance(d, str):
        return int(d.split('-')[0])
    return d.year


def _report_date(report) -> date:
    """Convierte report_date a objeto date para comparaciones de rango."""
    d = report.report_date
    if isinstance(d, str):
        return date.fromisoformat(d)
    if isinstance(d, datetime):
        return d.date()
    return d


def _sum_nested_key(obj, key: str) -> float:
    total = 0.0
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                try:
                    total += float(v)
                except (ValueError, TypeError):
                    pass
            else:
                total += _sum_nested_key(v, key)
    elif isinstance(obj, list):
        for item in obj:
            total += _sum_nested_key(item, key)
    return total


def _parse_indicator_ids(field_name) -> list:
    """
    Convierte `metric.field_name` en una lista de enteros (IDs de indicador).

    Formatos aceptados (retrocompatibles):
      - "76"               → [76]
      - "163,162,164"      → [163, 162, 164]
      - "163, 162 , 164"   → [163, 162, 164]
      - "[163,162,164]"    → [163, 162, 164]  (JSON array)
      - [163, 162, 164]    → [163, 162, 164]  (lista ya parseada)
      - 76                 → [76]              (número directo)

    Devuelve una lista vacía si no se puede extraer ningún entero.
    Se preserva el orden y se eliminan duplicados.
    """
    if field_name is None:
        return []

    # Ya es una lista/tupla: extraer enteros.
    if isinstance(field_name, (list, tuple)):
        ids = []
        for item in field_name:
            try:
                ids.append(int(str(item).strip()))
            except (ValueError, TypeError):
                continue
        return _dedup_preserve_order(ids)

    # Entero directo.
    if isinstance(field_name, int) and not isinstance(field_name, bool):
        return [field_name]

    text = str(field_name).strip()
    if not text:
        return []

    # JSON array: "[163, 162]"
    if text.startswith('[') and text.endswith(']'):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return _parse_indicator_ids(parsed)
        except (ValueError, TypeError):
            pass  # cae al parser CSV / regex

    # CSV / mixto: extraer todos los enteros que aparezcan.
    tokens = re.findall(r'-?\d+', text)
    ids = []
    for t in tokens:
        try:
            ids.append(int(t))
        except ValueError:
            continue
    return _dedup_preserve_order(ids)


def _dedup_preserve_order(seq):
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _sum_any_numeric(obj) -> float:
    """
    Suma todos los valores numéricos encontrados dentro de una estructura
    arbitraria (dict/list/number/string-numérico). Usado cuando un
    indicator_value guarda una estructura tipo "sum_group" (p. ej.
    {"enero": 50, "febrero": 30, ...}) en lugar de un número plano.

    Ignora valores booleanos (True/False serían sumados como 1/0 por
    float(), lo cual no es lo deseado en datos agregados).
    """
    if obj is None or isinstance(obj, bool):
        return 0.0
    if isinstance(obj, (int, float)):
        return float(obj)
    if isinstance(obj, str):
        try:
            return float(obj)
        except (ValueError, TypeError):
            return 0.0
    if isinstance(obj, dict):
        return sum(_sum_any_numeric(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_sum_any_numeric(item) for item in obj)
    return 0.0