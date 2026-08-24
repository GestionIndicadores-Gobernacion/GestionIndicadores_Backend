"""
Consolidado de indicadores por **municipio × año**.

Reutiliza los mismos acumuladores que
`ReportIndicatorHandler.aggregate_indicators_by_component` (`accumulators.py`),
de modo que los totales que aparecen en la tabla consolidada son idénticos a
los que ya dibuja el explorador de indicadores para ese mismo periodo. La
única diferencia es la granularidad: en vez de un único bucket para el rango
filtrado, se construye un bucket por cada par ``(año, municipio)``.

Los años **no se hardcodean**: salen de `Report.report_date` de los reportes
realmente registrados para el componente. Si mañana aparecen reportes de 2027,
2027 se agrega solo.
"""

from collections import defaultdict
from unicodedata import normalize as _unicode_normalize

from sqlalchemy import extract
from sqlalchemy.orm import joinedload, selectinload

from app.modules.indicators.models.Component.component import Component
from app.modules.indicators.models.Report.report import Report
from app.modules.indicators.models.Report.report_indicator_value import (
    ReportIndicatorValue,
)

from .accumulators import make_accumulator, process_indicator_value


# Tipos que `process_indicator_value` sabe convertir a un total numérico.
# El resto (text, date, file_attachment...) entra al acumulador con
# `by_month` vacío y no aporta nada a un consolidado.
AGGREGATABLE_FIELD_TYPES = {
    "number",
    "sum_group",
    "grouped_data",
    "select",
    "multi_select",
    "categorized_group",
    "dataset_select",
    "dataset_multi_select",
}

# Tipos cuyo desglose vive en `by_category` (el de `categorized_group`
# vive en `by_metric`).
CATEGORY_BREAKDOWN_TYPES = {
    "sum_group",
    "grouped_data",
    "select",
    "multi_select",
    "dataset_select",
    "dataset_multi_select",
}

NO_LOCATION_LABEL = "Sin municipio"


def _location_key(raw: str | None) -> str:
    """Clave de agrupación insensible a mayúsculas/tildes/espacios.

    Evita que "CALI", "Cali" y "Calí" produzcan tres filas distintas en un
    consolidado que se va a imprimir. La etiqueta que se muestra es la
    grafía original más frecuente (ver `_pick_label`).
    """
    text = (raw or "").strip()
    if not text:
        return ""
    folded = _unicode_normalize("NFD", text.lower())
    folded = "".join(c for c in folded if not 0x0300 <= ord(c) <= 0x036F)
    return " ".join(folded.split())


def _pick_label(counter: dict[str, int]) -> str:
    """Grafía original más usada; empate → orden alfabético estable."""
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def _round(value: float) -> float:
    """Redondea a 2 y devuelve int cuando el valor es entero.

    Los indicadores de este dominio son conteos; devolver ``250`` en vez de
    ``250.0`` mantiene el JSON limpio para la tabla impresa.
    """
    rounded = round(value or 0, 2)
    return int(rounded) if rounded == int(rounded) else rounded


class ReportConsolidatedHandler:

    @staticmethod
    def by_location_year(
        component_id: int,
        indicator_id: int | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> dict:
        """Matriz municipio × año para cada indicador agregable del componente.

        :param indicator_id: si se pasa, la respuesta trae solo ese indicador.
        :param year_from / year_to: recorte opcional del rango de años. Sin
            ellos se devuelven **todos** los años con reportes.
        """
        component = Component.query.get(component_id)
        if not component:
            return None

        query = (
            Report.query
            .options(
                selectinload(Report.indicator_values)
                .joinedload(ReportIndicatorValue.indicator)
            )
            .filter(Report.component_id == component_id)
        )
        if year_from is not None:
            query = query.filter(extract("year", Report.report_date) >= year_from)
        if year_to is not None:
            query = query.filter(extract("year", Report.report_date) <= year_to)

        reports = query.order_by(Report.report_date.asc()).all()

        base = {
            "component_id": component_id,
            "component_name": component.name,
            "strategy_id": component.strategy_id,
            "strategy_name": component.strategy.name if component.strategy else None,
            "years": [],
            "total_reports": len(reports),
            "reports_by_location": [],
            "reports_totals_by_year": {},
            "indicators": [],
        }
        if not reports:
            return base

        # ── Buckets (año, municipio) ────────────────────────────────────
        # Cada bucket tiene su propio acumulador; `process_indicator_value`
        # se encarga de la semántica por field_type (la misma que usa el
        # explorador), así no se duplica lógica de cálculo aquí.
        buckets: dict[tuple[int, str], dict] = {}
        label_counter: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        report_counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        years: set[int] = set()

        # Descartables: `process_indicator_value` los exige pero el
        # consolidado no los usa (el desglose sale de `by_metric` /
        # `by_category`, que ya vienen scoped al bucket).
        for r in reports:
            year = r.report_date.year
            years.add(year)

            raw_location = (r.intervention_location or "").strip()
            key = _location_key(raw_location)
            if key:
                label_counter[key][raw_location] += 1
            else:
                key = ""

            report_counts[key][year] += 1

            bucket = buckets.get((year, key))
            if bucket is None:
                bucket = {
                    "acc": make_accumulator(),
                    "location_indicator": defaultdict(lambda: defaultdict(float)),
                    "location_nested": defaultdict(
                        lambda: defaultdict(lambda: defaultdict(float))
                    ),
                    "actor_location": defaultdict(
                        lambda: defaultdict(lambda: defaultdict(int))
                    ),
                    "report_values": defaultdict(dict),
                }
                buckets[(year, key)] = bucket

            month_key = r.report_date.strftime("%Y-%m")
            for iv in r.indicator_values:
                if not iv.indicator:
                    continue
                if indicator_id is not None and iv.indicator_id != indicator_id:
                    continue
                process_indicator_value(
                    iv, iv.indicator, r, month_key,
                    bucket["acc"],
                    bucket["location_indicator"],
                    bucket["location_nested"],
                    bucket["actor_location"],
                    bucket["report_values"],
                    # El mapa de datasets solo alimenta *etiquetas* de
                    # dataset_select; el total (+1 por registro) no depende
                    # de él, así que evitamos cargar todos los records.
                    {},
                )

        sorted_years = sorted(years)

        # ── Etiquetas de municipio ──────────────────────────────────────
        labels: dict[str, str] = {
            key: _pick_label(variants) for key, variants in label_counter.items()
        }
        labels[""] = NO_LOCATION_LABEL

        def _sort_key(loc_key: str) -> tuple[int, str]:
            # "Sin municipio" siempre al final del listado impreso.
            return (1, "") if loc_key == "" else (0, labels[loc_key])

        # ── Conteo de reportes por municipio/año ────────────────────────
        reports_rows = []
        reports_totals: dict[int, int] = defaultdict(int)
        for loc_key in sorted(report_counts.keys(), key=_sort_key):
            per_year = report_counts[loc_key]
            row_total = 0
            by_year = {}
            for y in sorted_years:
                count = per_year.get(y, 0)
                by_year[str(y)] = count
                reports_totals[y] += count
                row_total += count
            reports_rows.append({
                "location": labels[loc_key],
                "by_year": by_year,
                "total": row_total,
            })

        base["years"] = sorted_years
        base["reports_by_location"] = reports_rows
        base["reports_totals_by_year"] = {
            str(y): reports_totals.get(y, 0) for y in sorted_years
        }

        # ── Matriz por indicador ────────────────────────────────────────
        meta: dict[int, dict] = {}
        # ind_id -> loc_key -> year -> total
        totals: dict[int, dict[str, dict[int, float]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(float))
        )
        # ind_id -> loc_key -> breakdown_key -> year -> total
        breakdowns: dict[int, dict[str, dict[str, dict[int, float]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        )

        for (year, loc_key), bucket in buckets.items():
            for ind_id, acc in bucket["acc"].items():
                field_type = acc.get("field_type")
                if field_type not in AGGREGATABLE_FIELD_TYPES:
                    continue

                meta.setdefault(ind_id, {
                    "indicator_id": ind_id,
                    "indicator_name": acc.get("name"),
                    "field_type": field_type,
                })

                totals[ind_id][loc_key][year] += sum(acc["by_month"].values())

                if field_type == "categorized_group":
                    source = acc["by_metric"]
                elif field_type in CATEGORY_BREAKDOWN_TYPES:
                    source = acc["by_category"]
                else:
                    source = {}

                for bk, value in source.items():
                    breakdowns[ind_id][loc_key][bk][year] += value

        indicators = []
        for ind_id, info in meta.items():
            per_location = totals[ind_id]
            bd_location = breakdowns[ind_id]

            rows = []
            totals_by_year: dict[int, float] = defaultdict(float)
            grand_total = 0.0
            breakdown_totals: dict[str, float] = defaultdict(float)

            for loc_key in sorted(per_location.keys(), key=_sort_key):
                per_year = per_location[loc_key]
                by_year = {}
                row_total = 0.0
                for y in sorted_years:
                    value = per_year.get(y, 0.0)
                    by_year[str(y)] = _round(value)
                    totals_by_year[y] += value
                    row_total += value
                grand_total += row_total

                bd_by_year = {}
                bd_total = {}
                for bk, per_year_bd in bd_location.get(loc_key, {}).items():
                    bd_row_total = 0.0
                    bd_by_year[bk] = {}
                    for y in sorted_years:
                        value = per_year_bd.get(y, 0.0)
                        bd_by_year[bk][str(y)] = _round(value)
                        bd_row_total += value
                    bd_total[bk] = _round(bd_row_total)
                    breakdown_totals[bk] += bd_row_total

                rows.append({
                    "location": labels[loc_key],
                    "by_year": by_year,
                    "total": _round(row_total),
                    "breakdown_by_year": bd_by_year,
                    "breakdown_total": bd_total,
                })

            # Un indicador sin un solo valor distinto de cero no aporta
            # nada a la tabla impresa.
            if grand_total == 0 and not breakdown_totals:
                continue

            indicators.append({
                **info,
                "rows": rows,
                "totals_by_year": {
                    str(y): _round(totals_by_year.get(y, 0.0)) for y in sorted_years
                },
                "grand_total": _round(grand_total),
                "breakdown_keys": [
                    {"key": bk, "total": _round(total)}
                    for bk, total in sorted(
                        breakdown_totals.items(), key=lambda kv: (-kv[1], kv[0])
                    )
                ],
            })

        indicators.sort(key=lambda i: (-(i["grand_total"] or 0), i["indicator_id"]))
        base["indicators"] = indicators
        return base
