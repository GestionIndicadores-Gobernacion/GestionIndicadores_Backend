# app/modules/indicators/services/strategy_progress_service.py

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

        try:
            indicator_id = int(metric.field_name)
        except (ValueError, TypeError):
            return 0.0

        query = Report.query.filter_by(strategy_id=strategy.id)
        if metric.component_id:
            query = query.filter_by(component_id=metric.component_id)

        reports = StrategyProgressService._filter_reports(
            query, current_year, date_from, date_to
        )

        total = 0.0
        for r in reports:
            iv = next(
                (v for v in (r.indicator_values or []) if v.indicator_id == indicator_id),
                None
            )
            if iv is None or iv.value is None:
                continue
            try:
                total += float(iv.value)
            except (ValueError, TypeError):
                pass

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

        try:
            indicator_id = int(metric.field_name)
        except (ValueError, TypeError):
            return 0.0

        query = Report.query.filter_by(strategy_id=strategy.id)
        if metric.component_id:
            query = query.filter_by(component_id=metric.component_id)

        reports = StrategyProgressService._filter_reports(
            query, current_year, date_from, date_to
        )

        total = 0.0
        for r in reports:
            iv = next(
                (v for v in (r.indicator_values or []) if v.indicator_id == indicator_id),
                None
            )
            if iv is None or not isinstance(iv.value, dict):
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