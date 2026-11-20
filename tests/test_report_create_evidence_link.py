"""Guardado de reportes "NIÑOS CAPACITADOS" (componente Promotores PYBA).

Regresión del "Error al guardar" genérico: el payload de indicadores era
válido, pero el `evidence_link` ya pertenecía a otro reporte y el backend
respondía 400 `{message: {evidence_link: "..."}}` que el frontend no
mostraba. Cubre:

- El payload con show_if (select → sum_group + multi_select) se guarda y
  persiste; los indicadores numéricos ocultos por show_if no se exigen.
- Un segundo reporte con el mismo enlace → 400 con el motivo en
  `message.evidence_link` (la validación de unicidad se mantiene).
- Editar el propio reporte conservando su enlace sigue permitido.
"""
import json
from datetime import date

import pytest

from app.core.extensions import db
from tests.test_admin_d1_endpoints import _seed, _make_user, _login

LINK = "https://drive.google.com/drive/folders/1aL7klXzPdvaDq3QBmxIn73E0j1ZapGRA?usp=drive_link"
SELECTOR = "¿QUÉ SE VA A REPORTAR?"
GUIAS = [
    "GUÍA 1: PRÁCTICAS RESPONSABLES DE CONVIVENCIA CON LOS ANIMALES",
    "GUÍA 2: PREVENCIÓN DEL MALTRATO ANIMAL",
    "GUÍA 3: ANIMALES EN SITUACIÓN DE CALLE",
]


@pytest.fixture()
def env(app, client):
    from app.modules.indicators.models.Strategy.strategy import Strategy
    from app.modules.indicators.models.Component.component import Component
    from app.modules.indicators.models.Component.component_indicator import ComponentIndicator
    from app.modules.indicators.models.Component.component_indicator_target import (
        ComponentIndicatorTarget,
    )
    from app.modules.indicators.models.Report.report import Report
    from app.modules.indicators.models.Report.report_indicator_value import ReportIndicatorValue
    from app.shared.models.audit_log import AuditLog

    _seed(app)
    _make_user(app, "admin", "rce-admin@x.co")
    token = _login(client, "rce-admin@x.co", "pw")

    st = Strategy(name="EDUCACIÓN PYBA (test)", objective="o", product_goal_description="p")
    db.session.add(st)
    db.session.flush()
    comp = Component(name="Promotores PYBA (test)", strategy_id=st.id)
    db.session.add(comp)
    db.session.flush()

    show_personas = {"indicator_name": SELECTOR, "value": "PERSONAS CAPACITADAS"}
    show_ninos = {"indicator_name": SELECTOR, "value": "NIÑOS CAPACITADOS"}
    personas = ComponentIndicator(
        component_id=comp.id, name="NO DE PERSONAS CAPACITADAS", field_type="number",
        is_required=True, config={"show_if": show_personas},
    )
    selector = ComponentIndicator(
        component_id=comp.id, name=SELECTOR, field_type="select", is_required=True,
        config={"options": ["PERSONAS CAPACITADAS", "NIÑOS CAPACITADOS"]},
    )
    ninos = ComponentIndicator(
        component_id=comp.id, name="NO DE NIÑOS Y NIÑAS CAPACITADOS", field_type="sum_group",
        is_required=True, config={"fields": ["Niños", "Niñas"], "show_if": show_ninos},
    )
    tematicas = ComponentIndicator(
        component_id=comp.id, name="TEMATICAS IMPLEMENTADAS NIÑOS", field_type="multi_select",
        is_required=True, config={"options": GUIAS, "show_if": show_ninos},
    )
    db.session.add_all([personas, selector, ninos, tematicas])
    db.session.flush()
    db.session.add_all([
        ComponentIndicatorTarget(indicator_id=personas.id, year=2026, target_value=3000),
        ComponentIndicatorTarget(indicator_id=ninos.id, year=2026, target_value=3000),
    ])
    db.session.commit()

    def payload(link=LINK):
        return {
            "strategy_id": st.id,
            "component_id": comp.id,
            "report_date": "2026-11-19",
            "executive_summary": "Capacitación en institución educativa",
            "intervention_location": "Cali",
            "zone_type": "Urbana",
            "evidence_link": link,
            "action_plan_activity_id": None,
            "indicator_values": [
                {"indicator_id": selector.id, "value": "NIÑOS CAPACITADOS"},
                {"indicator_id": ninos.id, "value": {"Niños": 10, "Niñas": 12}},
                {"indicator_id": tematicas.id, "value": GUIAS},
            ],
        }

    yield {"token": token, "payload": payload, "ninos": ninos}

    db.session.query(ReportIndicatorValue).delete()
    db.session.query(Report).delete()
    db.session.query(AuditLog).filter_by(entity="report").delete()
    db.session.query(ComponentIndicatorTarget).delete()
    db.session.query(ComponentIndicator).delete()
    db.session.query(Component).delete()
    db.session.query(Strategy).delete()
    db.session.commit()


def _send(client, method, url, token, body):
    return getattr(client, method)(
        url, data=json.dumps(body), content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_ninos_capacitados_se_guarda_y_persiste(client, env):
    from app.modules.indicators.models.Report.report import Report

    resp = _send(client, "post", "/reports/", env["token"], env["payload"]())
    assert resp.status_code == 201, resp.get_data(as_text=True)

    report = db.session.get(Report, resp.get_json()["id"])
    assert report.evidence_link == LINK
    assert report.report_date == date(2026, 11, 19)
    values = {iv.indicator_id: iv.value for iv in report.indicator_values}
    assert values[env["ninos"].id] == {"Niños": 10, "Niñas": 12}
    assert len(values) == 3


def test_enlace_de_evidencia_duplicado_devuelve_motivo_explicito(client, env):
    first = _send(client, "post", "/reports/", env["token"], env["payload"]())
    assert first.status_code == 201
    first_id = first.get_json()["id"]

    dup = _send(client, "post", "/reports/", env["token"], env["payload"]())
    assert dup.status_code == 400
    message = dup.get_json()["message"]
    assert isinstance(message, dict)
    assert f"reporte #{first_id}" in message["evidence_link"]
    # El motivo es funcional, no un volcado de SQL.
    assert "database" not in message

    # Con un enlace distinto, el mismo contenido sí se guarda.
    ok = _send(client, "post", "/reports/", env["token"], env["payload"](LINK + "&b=1"))
    assert ok.status_code == 201


def test_editar_reporte_conserva_su_propio_enlace(client, env):
    created = _send(client, "post", "/reports/", env["token"], env["payload"]())
    report_id = created.get_json()["id"]

    body = env["payload"]()
    body["executive_summary"] = "Resumen corregido"
    resp = _send(client, "put", f"/reports/{report_id}", env["token"], body)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["executive_summary"] == "Resumen corregido"


def test_fallo_de_bd_no_expone_sql_y_queda_en_log(client, env, monkeypatch, caplog):
    """Un error de BD durante el guardado responde un mensaje genérico; el
    detalle técnico solo va al log del servidor."""
    def _boom():
        raise RuntimeError('relation "secret_table" violates constraint xyz')

    monkeypatch.setattr(db.session, "commit", _boom)
    with caplog.at_level("ERROR"):
        resp = _send(client, "post", "/reports/", env["token"], env["payload"]())

    assert resp.status_code == 400
    body = resp.get_data(as_text=True)
    assert "secret_table" not in body
    assert "Error interno al guardar el reporte" in resp.get_json()["message"]["database"]
    assert any("secret_table" in (r.exc_text or "") or "ReportHandler.create failed" in r.getMessage()
               for r in caplog.records)
