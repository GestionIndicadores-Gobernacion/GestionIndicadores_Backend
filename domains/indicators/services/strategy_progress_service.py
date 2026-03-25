from datetime import datetime
import re

from domains.datasets.models.dataset import Dataset
from domains.datasets.models.record import Record
from domains.indicators.models.Strategy.strategy import Strategy
from domains.indicators.models.Report.report import Report


class StrategyProgressService:

    @staticmethod
    def get_progress(strategy: Strategy) -> dict:
        """
        Calcula el progreso de una estrategia para el año en curso.
        """

        current_year = datetime.utcnow().year

        goal_for_year = StrategyProgressService._get_goal_for_year(
            strategy,
            current_year
        )

        actual = StrategyProgressService._calculate_actual(
            strategy,
            current_year
        )

        percent = 0.0

        if goal_for_year and goal_for_year > 0:
            percent = round((actual / float(goal_for_year)) * 100, 2)

        return {
            "current_year": current_year,
            "current_year_number": StrategyProgressService._get_year_number(strategy, current_year),
            "current_year_goal": float(goal_for_year) if goal_for_year else 0.0,
            "current_year_actual": actual,
            "percent": min(percent, 100.0),
        }

    # ---------------------------------------------------------
    # METAS PROGRAMADAS
    # ---------------------------------------------------------

    @staticmethod
    def _get_year_number(strategy: Strategy, calendar_year: int) -> int | None:

        base_year = strategy.created_at.year
        number = calendar_year - base_year + 1

        return number if number >= 1 else None

    @staticmethod
    def _get_goal_for_year(strategy: Strategy, calendar_year: int):

        year_number = StrategyProgressService._get_year_number(
            strategy,
            calendar_year
        )

        if year_number is None:
            return None

        goal = next(
            (g for g in strategy.annual_goals if g.year_number == year_number),
            None
        )

        return goal.value if goal else None

    # ---------------------------------------------------------
    # CALCULO REAL
    # ---------------------------------------------------------

    @staticmethod
    def _calculate_actual(strategy: Strategy, current_year: int) -> float:

        total = 0.0

        for metric in strategy.metrics:

            total += StrategyProgressService._calculate_metric(
                metric,
                strategy,
                current_year
            )

        return total

    @staticmethod
    def _calculate_metric(metric, strategy: Strategy, current_year: int) -> float:

        t = metric.metric_type

        if t == "report_count":
            return StrategyProgressService._report_count(metric, strategy, current_year)

        if t == "report_sum":
            return StrategyProgressService._report_sum(metric, strategy, current_year)

        if t == "dataset_count":
            return StrategyProgressService._dataset_count(metric, current_year)

        if t == "dataset_sum":
            return StrategyProgressService._dataset_sum(metric, current_year)

        if t == "manual":
            return float(metric.manual_value or 0)

        return 0.0

    # ---------------------------------------------------------
    # REPORTES
    # ---------------------------------------------------------

    @staticmethod
    def _report_count(metric, strategy: Strategy, current_year: int) -> float:

        query = Report.query.filter_by(
            strategy_id=strategy.id
        )

        if metric.component_id:
            query = query.filter_by(component_id=metric.component_id)

        reports = [
            r for r in query.all()
            if _report_year(r) == current_year
        ]

        return float(len(reports))

    @staticmethod
    def _report_sum(metric, strategy: Strategy, current_year: int) -> float:

        if not metric.field_name:
            return 0.0

        query = Report.query.filter_by(
            strategy_id=strategy.id
        )

        if metric.component_id:
            query = query.filter_by(component_id=metric.component_id)

        reports = [
            r for r in query.all()
            if _report_year(r) == current_year
        ]

        total = 0.0

        for r in reports:

            val = _extract_indicator_value(r, metric.field_name)

            if val is not None:
                total += val

        return total

    # ---------------------------------------------------------
    # DATASETS
    # ---------------------------------------------------------

    @staticmethod
    def _dataset_count(metric, current_year: int) -> float:
        """
        Cuenta registros válidos de un dataset.
        """

        if not metric.dataset_id:
            return 0.0

        dataset = Dataset.query.get(metric.dataset_id)

        if not dataset:
            return 0.0

        match = re.search(r'\b(20\d{2})\b', dataset.name or '')

        if match and int(match.group(1)) != current_year:
            return 0.0

        records = Record.query.filter_by(
            dataset_id=dataset.id
        ).all()

        return float(sum(
            1 for r in records
            if r.data and r.data.get("mes") not in (None, "")
        ))

    @staticmethod
    def _dataset_sum(metric, current_year: int) -> float:
        """
        Suma una columna de un dataset.
        """

        if not metric.dataset_id or not metric.field_name:
            return 0.0

        dataset = Dataset.query.get(metric.dataset_id)

        if not dataset:
            return 0.0

        records = Record.query.filter_by(
            dataset_id=dataset.id
        ).all()

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


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _report_year(report) -> int:

    date = report.report_date

    if isinstance(date, str):
        return int(date.split("-")[0])

    return date.year


def _extract_indicator_value(report, field_name: str):

    for iv in (report.indicator_values or []):

        indicator = getattr(iv, "indicator", None)

        slug = getattr(indicator, "slug", None) or getattr(indicator, "name", None)

        if slug == field_name:

            try:
                return float(iv.value)
            except (ValueError, TypeError):
                return None

    return None