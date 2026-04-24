"""
Fuente de verdad de los KPIs del dashboard.

Replica bit-a-bit la semántica de `reports-kpi.service.ts` del frontend para
garantizar que al migrar a este endpoint los números NO cambien. Reutiliza
los helpers ya existentes en strategy_progress_service para estructuras
JSON complejas (sum_group / data anidada).

El frontend mantiene su lógica legacy como *fallback* durante la
migración; este servicio es la nueva fuente canónica.
"""

from datetime import datetime
from typing import Iterable, Tuple

from sqlalchemy import extract
from sqlalchemy.orm import selectinload

from app.modules.indicators.models.Report.report import Report
from app.modules.indicators.models.Report.report_indicator_value import (
    ReportIndicatorValue,
)
from app.modules.indicators.services.strategy_progress_service import (
    _sum_any_numeric,
    _sum_nested_key,
)


# ── Constantes de dominio (espejo del frontend) ─────────────────────────
COMPONENT_ID_ASISTENCIAS = 2
COMPONENT_ID_JUNTAS = 21
COMPONENT_ID_EMPRENDEDORES = 14
COMPONENT_ID_PROMOTORES = 22
COMPONENT_ID_NINOS = 23
COMPONENT_ID_ESTERILIZACION = 8
STRATEGY_ID_ESTERILIZACION = 3

ID_ASISTENCIAS_JUNTAS = 160
ID_DENUNCIAS_REPORTADAS = 137
ID_ANIMALES_ESTERILIZADOS = 99
ID_REFUGIOS = 102
ID_NINOS_CANTIDAD_IMPACTADA = 114
ID_PERSONAS_CAPACITADAS_PROMOTORES = 76
ID_NINOS_CAPACITADOS_PROMOTORES = 163

DATASET_ID_PERSONAS_CAPACITADAS = 8
ESPACIOS_ACOGIDA = {"albergue/refugio", "fundacion", "hogar de paso"}


class ReportKpiService:
    """
    Fuente canónica de los KPIs del dashboard. Todos los métodos aceptan
    ``year: int`` y devuelven valores numéricos comparables con los que
    el frontend producía en memoria para el mismo año.
    """

    # ─── Entrada principal ──────────────────────────────────────────────
    @staticmethod
    def get_snapshot(year: int) -> dict:
        reports = ReportKpiService._year_reports(year)
        return {
            "year": year,
            "asistencias_tecnicas": ReportKpiService._asistencias_tecnicas(reports),
            "denuncias_reportadas": ReportKpiService._denuncias_reportadas(reports),
            "personas_capacitadas": ReportKpiService._personas_capacitadas(year, reports),
            "ninos_sensibilizados": ReportKpiService._ninos_sensibilizados(reports),
            "animales_esterilizados": ReportKpiService._animales_esterilizados(reports),
            "refugios_impactados": ReportKpiService._refugios_impactados(reports),
            "emprendedores_cofinanciados": ReportKpiService._emprendedores_cofinanciados(reports),
        }

    @staticmethod
    def get_by_location(year: int) -> dict:
        """
        KPIs agrupados por `intervention_location`. No incluye
        `personas_capacitadas` porque su cálculo depende del dataset
        externo y no tiene granularidad por municipio hoy.

        Forma de respuesta:
        {
          "year": 2026,
          "items": [
            {
              "location": "Cali",
              "total_reports": 12,
              "asistencias_tecnicas": 3,
              "denuncias_reportadas": 1,
              "animales_esterilizados": 850,
              "refugios_impactados": 2,
              "ninos_sensibilizados": 120,
              "emprendedores_cofinanciados": 0
            },
            ...
          ]
        }
        """
        reports = ReportKpiService._year_reports(year)

        by_loc: dict[str, list] = {}
        for r in reports:
            key = (r.intervention_location or "").strip()
            if not key:
                continue
            by_loc.setdefault(key, []).append(r)

        items = []
        for location, reps in by_loc.items():
            items.append({
                "location": location,
                "total_reports": len(reps),
                "asistencias_tecnicas": ReportKpiService._asistencias_tecnicas(reps),
                "denuncias_reportadas": ReportKpiService._denuncias_reportadas(reps),
                "animales_esterilizados": ReportKpiService._animales_esterilizados(reps),
                "refugios_impactados": ReportKpiService._refugios_impactados(reps),
                "ninos_sensibilizados": ReportKpiService._ninos_sensibilizados(reps),
                "emprendedores_cofinanciados": ReportKpiService._emprendedores_cofinanciados(reps),
            })

        # Orden estable por location para que el frontend no "salte".
        items.sort(key=lambda it: it["location"])
        return {"year": year, "items": items}

    # ─── Helpers internos ───────────────────────────────────────────────
    @staticmethod
    def _year_reports(year: int):
        """Carga todos los reportes del año con sus indicator_values
        eager-loaded (evita N+1). Equivale al ``filterByYear`` del
        frontend, pero a nivel SQL."""
        return (
            Report.query
            .options(selectinload(Report.indicator_values))
            .filter(extract("year", Report.report_date) == year)
            .all()
        )

    @staticmethod
    def _iv_for(report, indicator_id: int):
        return next(
            (v for v in (report.indicator_values or []) if v.indicator_id == indicator_id),
            None,
        )

    # ─── 1. Asistencias técnicas ────────────────────────────────────────
    @staticmethod
    def _asistencias_tecnicas(reports: Iterable[Report]) -> int:
        total = 0.0
        for r in reports:
            if r.component_id == COMPONENT_ID_ASISTENCIAS:
                total += 1
                continue
            if r.component_id == COMPONENT_ID_JUNTAS:
                iv = ReportKpiService._iv_for(r, ID_ASISTENCIAS_JUNTAS)
                if iv is None or iv.value is None:
                    continue
                try:
                    total += float(iv.value)
                except (ValueError, TypeError):
                    pass
        return int(total)

    # ─── 2. Denuncias reportadas ────────────────────────────────────────
    @staticmethod
    def _denuncias_reportadas(reports: Iterable[Report]) -> int:
        total = 0.0
        for r in reports:
            iv = ReportKpiService._iv_for(r, ID_DENUNCIAS_REPORTADAS)
            if iv is None or iv.value is None:
                continue
            try:
                total += float(iv.value)
            except (ValueError, TypeError):
                pass
        return int(total)

    # ─── 3. Personas capacitadas ────────────────────────────────────────
    @staticmethod
    def _personas_capacitadas(year: int, reports: Iterable[Report]) -> int:
        from_reports = 0.0
        ind_id = (
            ID_NINOS_CAPACITADOS_PROMOTORES
            if year == 2026
            else ID_PERSONAS_CAPACITADAS_PROMOTORES
        )
        for r in reports:
            if r.component_id != COMPONENT_ID_PROMOTORES:
                continue
            iv = ReportKpiService._iv_for(r, ind_id)
            if iv is None or iv.value is None:
                continue
            if year == 2026:
                # Formato sum_group / estructurado: sumar cualquier numérico.
                from_reports += _sum_any_numeric(iv.value)
            else:
                try:
                    from_reports += float(iv.value)
                except (ValueError, TypeError):
                    pass

        # Dataset externo "Personas Capacitadas"
        dataset_year, records_with_mes = ReportKpiService._dataset_personas_capacitadas()
        if year == 2026:
            from_dataset = records_with_mes
        else:
            from_dataset = records_with_mes if dataset_year == year else 0

        return int(from_reports + from_dataset)

    @staticmethod
    def _dataset_personas_capacitadas() -> Tuple[int | None, int]:
        """Devuelve (año detectado en el nombre del dataset, cantidad de
        registros con campo 'mes' no vacío)."""
        import re
        from app.modules.datasets.models.dataset import Dataset
        from app.modules.datasets.models.table import Table
        from app.modules.datasets.models.record import Record

        ds = Dataset.query.get(DATASET_ID_PERSONAS_CAPACITADAS)
        if not ds:
            return None, 0
        match = re.search(r"\b(20\d{2})\b", ds.name or "")
        dataset_year = int(match.group(1)) if match else None

        # El servicio dataset_count (backend actual) filtra por la primera
        # tabla activa — replicamos la misma convención.
        table = Table.query.filter_by(dataset_id=ds.id, active=True).first()
        if not table:
            return dataset_year, 0
        records = Record.query.filter_by(table_id=table.id).all()
        count = sum(
            1 for r in records
            if r.data and r.data.get("mes") not in (None, "")
        )
        return dataset_year, count

    # ─── 4. Niños sensibilizados ────────────────────────────────────────
    @staticmethod
    def _ninos_sensibilizados(reports: Iterable[Report]) -> int:
        total = 0.0
        for r in reports:
            if r.component_id != COMPONENT_ID_NINOS:
                continue
            iv = ReportKpiService._iv_for(r, ID_NINOS_CANTIDAD_IMPACTADA)
            if iv is None or iv.value is None:
                continue
            try:
                total += float(iv.value)
            except (ValueError, TypeError):
                pass
        return int(total)

    # ─── 5. Animales esterilizados ──────────────────────────────────────
    @staticmethod
    def _animales_esterilizados(reports: Iterable[Report]) -> int:
        total = 0.0
        for r in reports:
            if (
                r.strategy_id != STRATEGY_ID_ESTERILIZACION
                or r.component_id != COMPONENT_ID_ESTERILIZACION
            ):
                continue
            iv = ReportKpiService._iv_for(r, ID_ANIMALES_ESTERILIZADOS)
            if iv is None or not isinstance(iv.value, dict):
                continue
            data = iv.value.get("data")
            if not isinstance(data, dict):
                continue
            # Ya existe este helper: suma 'no_de_animales_esterilizados'
            # en cualquier profundidad dentro del dict.
            total += _sum_nested_key(data, "no_de_animales_esterilizados")
        return int(total)

    # ─── 6. Refugios impactados ─────────────────────────────────────────
    @staticmethod
    def _refugios_impactados(reports: Iterable[Report]) -> int:
        count = 0
        for r in reports:
            iv = ReportKpiService._iv_for(r, ID_REFUGIOS)
            if iv is None or iv.value is None:
                continue
            # El frontend compara iv.value (string) lowercased con el set
            # ESPACIOS_ACOGIDA. Replicamos exactamente el mismo criterio.
            val = iv.value
            if not isinstance(val, str):
                continue
            if val.strip().lower() in ESPACIOS_ACOGIDA:
                count += 1
        return count

    # ─── 7. Emprendedores cofinanciados ─────────────────────────────────
    @staticmethod
    def _emprendedores_cofinanciados(reports: Iterable[Report]) -> int:
        return sum(1 for r in reports if r.component_id == COMPONENT_ID_EMPRENDEDORES)
