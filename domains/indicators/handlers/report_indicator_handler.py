from collections import defaultdict
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import extract

from domains.indicators.models.Report.report import Report
from domains.indicators.models.Report.report_indicator_value import ReportIndicatorValue
from .accumulators import make_accumulator, process_indicator_value
from .serializers import (
    serialize_indicators, serialize_by_location,
    serialize_by_location_indicator, serialize_by_location_nested,
    serialize_by_actor_location
)
from .cross_indicators import build_cross_indicators, build_multiselect_cross


class ReportIndicatorHandler:

    @staticmethod
    def aggregate_indicators_by_component(component_id, year: int = None):
        from domains.indicators.models.Component.component import Component

        component = Component.query.get(component_id)
        if not component:
            from flask import jsonify
            return jsonify({"message": "Componente no encontrado"}), 404

        query = (
            Report.query
            .options(selectinload(Report.indicator_values).joinedload(ReportIndicatorValue.indicator))
            .filter(Report.component_id == component_id)
        )
        if year:
            query = query.filter(extract('year', Report.report_date) == year)

        reports = query.order_by(Report.report_date.asc()).all()

        if not reports:
            return {
                "component_id": component_id,
                "indicators": [],
                "by_location": [],
                "by_location_indicator": [],
                "by_location_nested": [],
                "by_actor_location": []
            }

        # ── Cargar datasets ──────────────────────────────────────────────────
        from domains.indicators.models.Component.component_indicator import ComponentIndicator
        from domains.datasets.models.record import Record
        from domains.datasets.models.table import Table

        ds_indicators = ComponentIndicator.query.filter_by(component_id=component_id).filter(
            ComponentIndicator.field_type.in_(["dataset_select", "dataset_multi_select"])
        ).all()

        dataset_record_map: dict[int, dict[int, dict]] = {}
        for ds_ind in ds_indicators:
            cfg = ds_ind.config or {}
            dataset_id = cfg.get("dataset_id")
            if not dataset_id or dataset_id in dataset_record_map:
                continue
            tables = Table.query.filter_by(dataset_id=dataset_id).all()
            table_ids = [t.id for t in tables]
            if not table_ids:
                continue
            records = Record.query.filter(Record.table_id.in_(table_ids)).all()
            dataset_record_map[dataset_id] = {r.id: r.data for r in records}

        # ── Acumuladores ────────────────────────────────────────────────────
        accumulator = make_accumulator()
        location_counts    = defaultdict(int)
        location_indicator = defaultdict(lambda: defaultdict(float))
        location_nested    = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        actor_location_acc = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        report_value_map   = defaultdict(dict)

        # ── Loop principal ───────────────────────────────────────────────────
        for r in reports:
            month_key = r.report_date.strftime("%Y-%m")

            if r.intervention_location:
                location_counts[r.intervention_location] += 1

            for iv in r.indicator_values:
                if not iv.indicator:
                    continue
                process_indicator_value(
                    iv, iv.indicator, r, month_key,
                    accumulator, location_indicator, location_nested,
                    actor_location_acc, report_value_map, dataset_record_map
                )

        # ── Serializar ───────────────────────────────────────────────────────
        all_months = sorted({r.report_date.strftime("%Y-%m") for r in reports})

        result = build_cross_indicators(component_id, reports, report_value_map)

        # ── Cruces especiales multi_select × number ──────────────────────────
        if component_id == 23:
            cross = build_multiselect_cross(
                reports, 115, 114, -11005, "Niños impactados por rango de edad"
            )
            if cross:
                result.append(cross)

        # ← una sola vez al final
        result += serialize_indicators(accumulator, all_months)

        return {
            "component_id":          component_id,
            "indicators":            result,
            "by_location":           serialize_by_location(location_counts),
            "by_location_indicator": serialize_by_location_indicator(location_indicator),
            "by_location_nested":    serialize_by_location_nested(location_nested),
            "by_actor_location":     serialize_by_actor_location(actor_location_acc, accumulator),
        }