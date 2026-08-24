"""
Consolidado municipio x año (`ReportConsolidatedHandler.by_location_year`).

Cubre lo que pidió negocio: los años salen de `report_date` (nunca
hardcodeados), la fila por municipio suma los años disponibles y el
desglose por metrica de `categorized_group` cuadra con el total.
"""

from datetime import date

import pytest

from app.core.extensions import db
from app.modules.indicators.models.Component.component import Component
from app.modules.indicators.models.Component.component_indicator import ComponentIndicator
from app.modules.indicators.models.Report.report import Report, ZoneTypeEnum
from app.modules.indicators.models.Report.report_indicator_value import ReportIndicatorValue
from app.modules.indicators.models.Strategy.strategy import Strategy
from app.modules.indicators.services.report_consolidated_handler import (
    ReportConsolidatedHandler,
)


@pytest.fixture()
def escenario(app):
    """Estrategia con un componente y dos indicadores, reportes 2025/2026."""
    strategy = Strategy(
        name="ATENCION PRIMARIA EN SALUD (test)",
        objective="obj",
        product_goal_description="meta",
    )
    db.session.add(strategy)
    db.session.flush()

    component = Component(strategy_id=strategy.id, name="ATENCION EQUIPO DE CAMPO (test)")
    db.session.add(component)
    db.session.flush()

    plano = ComponentIndicator(
        component_id=component.id, name="Personas asistidas",
        field_type="number", order=0,
    )
    animales = ComponentIndicator(
        component_id=component.id, name="Animales atendidos",
        field_type="categorized_group", order=1,
    )
    texto = ComponentIndicator(
        component_id=component.id, name="Nombre del refugio",
        field_type="text", order=2,
    )
    db.session.add_all([plano, animales, texto])
    db.session.flush()

    def _animal_value(esterilizados, vacunados):
        return {
            "data": {
                "CANINO": {
                    "Hembra": {
                        "no_de_animales_esterilizados": esterilizados,
                        "no_de_animales_vacunados": vacunados,
                    }
                }
            }
        }

    # (fecha, municipio, personas, esterilizados, vacunados)
    filas = [
        (date(2025, 3, 10), "Cali",          40,  60,  40),
        (date(2025, 7, 2),  "CALI",          20,  10,  10),   # misma ciudad, otra grafia
        (date(2025, 5, 5),  "Dagua",         30,  30,  20),
        (date(2026, 2, 1),  "Cali",          50,  90,  60),
        (date(2026, 4, 9),  "Buenaventura",  70,  50,  40),
        (date(2026, 6, 6),  "",              10,   5,   5),   # sin municipio
    ]

    for fecha, municipio, personas, esteril, vacunados in filas:
        report = Report(
            strategy_id=strategy.id,
            component_id=component.id,
            report_date=fecha,
            executive_summary="resumen",
            intervention_location=municipio,
            zone_type=ZoneTypeEnum.URBANA,
        )
        db.session.add(report)
        db.session.flush()
        db.session.add_all([
            ReportIndicatorValue(
                report_id=report.id, indicator_id=plano.id, value=personas,
            ),
            ReportIndicatorValue(
                report_id=report.id, indicator_id=animales.id,
                value=_animal_value(esteril, vacunados),
            ),
            ReportIndicatorValue(
                report_id=report.id, indicator_id=texto.id, value="Refugio X",
            ),
        ])

    db.session.commit()
    yield {"component": component, "plano": plano, "animales": animales, "texto": texto}

    db.session.query(ReportIndicatorValue).delete()
    db.session.query(Report).delete()
    db.session.query(ComponentIndicator).delete()
    db.session.query(Component).delete()
    db.session.query(Strategy).delete()
    db.session.commit()


def _indicator(result, indicator_id):
    return next(i for i in result["indicators"] if i["indicator_id"] == indicator_id)


def _row(indicator, location):
    return next(r for r in indicator["rows"] if r["location"] == location)


def test_years_salen_de_los_reportes(escenario):
    result = ReportConsolidatedHandler.by_location_year(escenario["component"].id)
    assert result["years"] == [2025, 2026]
    assert result["total_reports"] == 6


def test_matriz_por_municipio_y_consolidado(escenario):
    result = ReportConsolidatedHandler.by_location_year(escenario["component"].id)
    plano = _indicator(result, escenario["plano"].id)

    cali = _row(plano, "Cali")
    assert cali["by_year"] == {"2025": 60, "2026": 50}   # 40+20 en 2025
    assert cali["total"] == 110

    dagua = _row(plano, "Dagua")
    assert dagua["by_year"] == {"2025": 30, "2026": 0}
    assert dagua["total"] == 30

    bura = _row(plano, "Buenaventura")
    assert bura["by_year"] == {"2025": 0, "2026": 70}

    assert plano["totals_by_year"] == {"2025": 90, "2026": 130}
    assert plano["grand_total"] == 220
    assert plano["grand_total"] == sum(r["total"] for r in plano["rows"])


def test_reportes_sin_municipio_van_al_final(escenario):
    result = ReportConsolidatedHandler.by_location_year(escenario["component"].id)
    plano = _indicator(result, escenario["plano"].id)
    assert plano["rows"][-1]["location"] == "Sin municipio"
    assert plano["rows"][-1]["total"] == 10


def test_categorized_group_desglosa_por_metrica(escenario):
    result = ReportConsolidatedHandler.by_location_year(escenario["component"].id)
    animales = _indicator(result, escenario["animales"].id)

    cali = _row(animales, "Cali")
    # 2025: (60+40) + (10+10) = 120 ; 2026: 90+60 = 150
    assert cali["by_year"] == {"2025": 120, "2026": 150}
    assert cali["total"] == 270

    assert cali["breakdown_by_year"]["no_de_animales_esterilizados"] == {
        "2025": 70, "2026": 90,
    }
    assert cali["breakdown_total"]["no_de_animales_esterilizados"] == 160
    assert cali["breakdown_total"]["no_de_animales_vacunados"] == 110
    # El desglose por metrica debe sumar exactamente el total de la fila.
    assert sum(cali["breakdown_total"].values()) == cali["total"]

    keys = [k["key"] for k in animales["breakdown_keys"]]
    assert set(keys) == {
        "no_de_animales_esterilizados", "no_de_animales_vacunados",
    }


def test_indicadores_no_agregables_quedan_fuera(escenario):
    result = ReportConsolidatedHandler.by_location_year(escenario["component"].id)
    ids = {i["indicator_id"] for i in result["indicators"]}
    assert escenario["texto"].id not in ids


def test_filtro_por_indicador(escenario):
    result = ReportConsolidatedHandler.by_location_year(
        escenario["component"].id, indicator_id=escenario["plano"].id
    )
    assert [i["indicator_id"] for i in result["indicators"]] == [escenario["plano"].id]


def test_recorte_de_anios(escenario):
    result = ReportConsolidatedHandler.by_location_year(
        escenario["component"].id, year_from=2026
    )
    assert result["years"] == [2026]
    plano = _indicator(result, escenario["plano"].id)
    assert plano["totals_by_year"] == {"2026": 130}


def test_conteo_de_reportes_por_municipio(escenario):
    result = ReportConsolidatedHandler.by_location_year(escenario["component"].id)
    cali = next(r for r in result["reports_by_location"] if r["location"] == "Cali")
    assert cali["by_year"] == {"2025": 2, "2026": 1}
    assert cali["total"] == 3
    assert result["reports_totals_by_year"] == {"2025": 3, "2026": 3}


def test_componente_inexistente(app):
    assert ReportConsolidatedHandler.by_location_year(999999) is None


# ── Endpoint HTTP ────────────────────────────────────────────────────────

def test_endpoint_devuelve_la_matriz(client, app, escenario):
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(identity="1")

    resp = client.get(
        f"/reports/aggregate/component/{escenario['component'].id}/location-year",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)

    body = resp.get_json()
    assert body["years"] == [2025, 2026]
    assert body["component_id"] == escenario["component"].id
    assert body["strategy_name"] == "ATENCION PRIMARIA EN SALUD (test)"

    plano = next(
        i for i in body["indicators"] if i["indicator_id"] == escenario["plano"].id
    )
    cali = next(r for r in plano["rows"] if r["location"] == "Cali")
    assert cali["by_year"] == {"2025": 60, "2026": 50}
    assert cali["total"] == 110


def test_endpoint_requiere_jwt(client, escenario):
    resp = client.get(
        f"/reports/aggregate/component/{escenario['component'].id}/location-year"
    )
    assert resp.status_code == 401


def test_endpoint_404_componente_inexistente(client, app):
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(identity="1")

    resp = client.get(
        "/reports/aggregate/component/999999/location-year",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ── Paridad con el explorador ────────────────────────────────────────────

@pytest.mark.parametrize("year", [2025, 2026])
def test_totales_cuadran_con_el_explorador(escenario, year):
    """El consolidado no puede contradecir la gráfica que ya existe.

    `aggregate_indicators_by_component(year=Y)` es lo que alimenta el
    explorador; la columna Y del consolidado debe dar exactamente lo
    mismo para cada indicador.
    """
    from app.modules.indicators.services.report_indicator_handler import (
        ReportIndicatorHandler,
    )

    explorer = ReportIndicatorHandler.aggregate_indicators_by_component(
        escenario["component"].id, year=year
    )
    consolidated = ReportConsolidatedHandler.by_location_year(
        escenario["component"].id
    )

    explorer_totals = {
        ind["indicator_id"]: sum(m["total"] for m in ind.get("by_month", []))
        for ind in explorer["indicators"]
        if ind["indicator_id"] > 0
    }

    for ind in consolidated["indicators"]:
        expected = explorer_totals.get(ind["indicator_id"])
        assert expected is not None, f"indicador {ind['indicator_id']} ausente en el explorador"
        assert ind["totals_by_year"][str(year)] == expected
