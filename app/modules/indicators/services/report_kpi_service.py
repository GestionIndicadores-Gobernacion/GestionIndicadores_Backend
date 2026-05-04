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
    def get_snapshot(year: int, date_from: str | None = None, date_to: str | None = None) -> dict:
        reports = ReportKpiService._scoped_reports(year, date_from, date_to)
        return {
            "year": year,
            "asistencias_tecnicas": ReportKpiService._asistencias_tecnicas(reports),
            "denuncias_reportadas": ReportKpiService._denuncias_reportadas(year, reports),
            # NOTA: `personas_capacitadas` mezcla reportes (sí filtrados por
            # rango) + un dataset externo anual sin granularidad por fecha.
            # La parte del dataset se mantiene anclada al año; documentado en
            # `_personas_capacitadas`.
            "personas_capacitadas": ReportKpiService._personas_capacitadas(year, reports),
            "ninos_sensibilizados": ReportKpiService._ninos_sensibilizados(reports),
            "animales_esterilizados": ReportKpiService._animales_esterilizados(reports),
            "refugios_impactados": ReportKpiService._refugios_impactados(reports),
            "emprendedores_cofinanciados": ReportKpiService._emprendedores_cofinanciados(reports),
        }

    @staticmethod
    def get_by_location(year: int, date_from: str | None = None, date_to: str | None = None) -> dict:
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
        reports = ReportKpiService._scoped_reports(year, date_from, date_to)

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
                "denuncias_reportadas": ReportKpiService._denuncias_reportadas(year, reps),
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
    def _scoped_reports(year: int, date_from: str | None, date_to: str | None):
        """
        Si llega rango (`date_from`+`date_to`) lo respeta; en otro caso
        cae al filtro por año. Mantiene el eager-load de indicator_values.
        """
        if date_from and date_to:
            return (
                Report.query
                .options(selectinload(Report.indicator_values))
                .filter(
                    Report.report_date >= date_from,
                    Report.report_date <= date_to,
                )
                .all()
            )
        return ReportKpiService._year_reports(year)

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
    def _denuncias_reportadas(year: int, reports: Iterable[Report]) -> int:
        """Avance del KPI 'Denuncias reportadas'.

        Mismo patrón que `_personas_capacitadas`: la fuente real ahora es
        el dataset "REPORTE DENUNCIAS" (registros con `data.fecha`).

        - **2026 en adelante**: solo dataset, filtrado por año.
        - **Años anteriores**: reportes manuales (indicador 137) +
          dataset, para no perder valores históricos cargados antes de
          que existiera el dataset.
        """
        from_dataset = ReportKpiService._dataset_denuncias_count(year)

        if year >= 2026:
            return from_dataset

        from_reports = 0.0
        for r in reports:
            iv = ReportKpiService._iv_for(r, ID_DENUNCIAS_REPORTADAS)
            if iv is None or iv.value is None:
                continue
            try:
                from_reports += float(iv.value)
            except (ValueError, TypeError):
                pass
        return int(from_reports + from_dataset)

    @staticmethod
    def _dataset_denuncias_count(year: int) -> int:
        """Cuenta registros del dataset "REPORTE DENUNCIAS" cuyo año en
        cualquier campo de fecha disponible (Fecha, Fecha del presunto
        maltrato, Fecha del diligenciamiento) coincida con `year`.

        Mismo parser que `_year_from_fecha` de strategy_routes para que
        Dashboard y Cumplimiento muestren el mismo número.
        """
        import re
        from app.modules.datasets.models.dataset import Dataset
        from app.modules.datasets.models.table import Table
        from app.modules.datasets.models.record import Record
        from sqlalchemy import func

        def _year_from_value(v) -> int | None:
            if v is None or v == "":
                return None
            s = str(v).strip()
            m = re.match(r'^(\d{4})-\d{1,2}-\d{1,2}', s)
            if m: return int(m.group(1))
            m = re.match(r'^\d{1,2}/\d{1,2}/(\d{4})\b', s)
            if m: return int(m.group(1))
            m = re.match(r'^(\d{4})/\d{1,2}/\d{1,2}', s)
            if m: return int(m.group(1))
            m = re.search(r'\b(20\d{2})\b', s)
            if m: return int(m.group(1))
            return None

        def _record_year(data: dict) -> int | None:
            # Preferir campo "Fecha" (timestamp del registro). Fallback a
            # cualquier otro campo cuyo nombre normalizado contenga 'fecha'.
            preferred = data.get("fecha")
            y = _year_from_value(preferred)
            if y is not None:
                return y
            for k, v in data.items():
                if "fecha" in k.lower():
                    y = _year_from_value(v)
                    if y is not None:
                        return y
            return None

        ds = (
            Dataset.query
            .filter(func.upper(Dataset.name) == "REPORTE DENUNCIAS")
            .first()
        )
        if not ds:
            return 0
        # El analyzer marca como `denuncias` solo la hoja principal; aquí
        # iteramos todas las tablas activas y nos quedamos con la que tenga
        # el campo "numero_de_caso" para no contar hojas auxiliares.
        tables = Table.query.filter_by(dataset_id=ds.id, active=True).all()
        if not tables:
            return 0

        from app.modules.datasets.models.field import Field
        target_table_ids = []
        for t in tables:
            field_names = {f.name for f in Field.query.filter_by(table_id=t.id).all()}
            if any("numero_de_caso" in n for n in field_names):
                target_table_ids.append(t.id)
        if not target_table_ids:
            target_table_ids = [t.id for t in tables]

        total = 0
        for tid in target_table_ids:
            for r in Record.query.filter_by(table_id=tid).all():
                if r.data and _record_year(r.data) == year:
                    total += 1
        return total

    # ─── 3. Personas capacitadas ────────────────────────────────────────
    @staticmethod
    def _personas_capacitadas(year: int, reports: Iterable[Report]) -> int:
        """Avance del KPI 'Personas Capacitadas'.

        Reglas por año:

        - **2026 en adelante**: el equipo dejó de reportar manualmente
          el indicador 76 y todo lo nuevo se carga al dataset
          "PERSONAS CAPACITADAS CONSOLIDADO". El KPI cuenta SOLO los
          registros del dataset cuya `data.fecha` sea de ese año.
          (Para 2026 → 456). NO se suma el indicador 163 (niños) ni
          el 76 desde reportes para no duplicar con las otras tarjetas
          del dashboard de Cumplimiento.

        - **Años anteriores (2025 y previos)**: el dataset todavía no
          existía; los datos vivían en reportes manuales del indicador
          76 (plano). Se suma `reportes(ind 76) + dataset_filtered`
          para no perder los volúmenes históricos (2025 ≈ 3.500 + 18
          rezagados). Esa suma da el total real ingresado al sistema
          ese año.
        """
        from_dataset = ReportKpiService._dataset_personas_capacitadas_count(year)

        if year >= 2026:
            return from_dataset

        from_reports = 0.0
        for r in reports:
            if r.component_id != COMPONENT_ID_PROMOTORES:
                continue
            iv = ReportKpiService._iv_for(r, ID_PERSONAS_CAPACITADAS_PROMOTORES)
            if iv is None or iv.value is None:
                continue
            try:
                from_reports += float(iv.value)
            except (ValueError, TypeError):
                pass

        return int(from_reports + from_dataset)

    @staticmethod
    def _dataset_personas_capacitadas_count(year: int) -> int:
        """Cuenta los registros del dataset "PERSONAS CAPACITADAS
        CONSOLIDADO" cuya columna `fecha` pertenece al año pedido.

        Mismo parser que strategy_routes (single source of truth para
        que el KPI Card y el Dashboard de Cumplimiento siempre muestren
        el mismo número).
        """
        import re
        from app.modules.datasets.models.dataset import Dataset
        from app.modules.datasets.models.table import Table
        from app.modules.datasets.models.record import Record
        from sqlalchemy import func

        def _year_from_fecha(v) -> int | None:
            if v is None or v == "":
                return None
            s = str(v).strip()
            m = re.match(r'^(\d{4})-\d{1,2}-\d{1,2}', s)
            if m: return int(m.group(1))
            m = re.match(r'^\d{1,2}/\d{1,2}/(\d{4})\b', s)
            if m: return int(m.group(1))
            m = re.match(r'^(\d{4})/\d{1,2}/\d{1,2}', s)
            if m: return int(m.group(1))
            m = re.search(r'\b(20\d{2})\b', s)
            if m: return int(m.group(1))
            return None

        # Búsqueda por nombre (igual que strategy_routes), no por id
        # hardcodeado — el id puede cambiar entre entornos.
        ds = (
            Dataset.query
            .filter(func.upper(Dataset.name) == "PERSONAS CAPACITADAS CONSOLIDADO")
            .first()
        )
        if not ds:
            return 0
        table = Table.query.filter_by(dataset_id=ds.id, active=True).first()
        if not table:
            return 0
        records = Record.query.filter_by(table_id=table.id).all()
        return sum(
            1 for r in records
            if r.data and _year_from_fecha(r.data.get("fecha")) == year
        )

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
