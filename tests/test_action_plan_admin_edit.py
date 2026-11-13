"""Corrección administrativa de actividades ya reportadas.

Cubre:
- Autorización: solo rol admin con `action_plans.edit_reported`; monitor,
  editor y viewer bloqueados (aunque tengan el permiso por override); admin
  con el permiso revocado también bloqueado.
- Integridad: el reporte vinculado y sus valores de indicadores no cambian;
  reported_at / evidencia / descripción / score se conservan.
- Lista blanca: campos no permitidos → 422.
- Reglas de fecha: no posterior al reporte, mismo año, no reabrir plazo de
  evidencia vencido.
- Historial permanente por campo + motivo obligatorio.
- El endpoint normal `/edit` rechaza actividades reportadas (409).
"""
import json
from datetime import date, datetime, timedelta

import pytest

from app.core.extensions import db
from app.shared.permissions import PERM_ACTION_PLANS_EDIT_REPORTED

from tests.test_admin_d1_endpoints import _seed, _make_user, _login, _add_override


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _put(client, url, token, body):
    return client.put(url, data=json.dumps(body), content_type="application/json", headers=_h(token))


@pytest.fixture()
def env(app, client):
    """Plan con una actividad reportada (con reporte e indicador vinculados)
    y otra sin reportar. Devuelve ids + tokens por rol."""
    _seed(app)
    from app.modules.indicators.models.Strategy.strategy import Strategy
    from app.modules.indicators.models.Component.component import Component
    from app.modules.indicators.models.Report.report import Report, ZoneTypeEnum
    from app.modules.indicators.models.Report.report_indicator_value import ReportIndicatorValue
    from app.modules.action_plans.models.action_plan import (
        ActionPlan, ActionPlanObjective, ActionPlanActivity,
    )

    ids = {}
    for role in ("admin", "monitor", "editor", "viewer"):
        ids[role] = _make_user(app, role, f"ape-{role}@x.co")
    ids["admin2"] = _make_user(app, "admin", "ape-admin2@x.co")

    with app.app_context():
        st = Strategy(name="EDUCACIÓN PYBA", objective="o", product_goal_description="p")
        db.session.add(st)
        db.session.flush()
        comp = Component(name="PROMOTORES PYBA", strategy_id=st.id)
        db.session.add(comp)
        db.session.flush()
        plan = ActionPlan(strategy_id=st.id, component_id=comp.id, user_id=ids["editor"],
                          responsible="Promotor")
        db.session.add(plan)
        db.session.flush()
        obj = ActionPlanObjective(action_plan_id=plan.id, objective_text="CAPACITACIÓN")
        db.session.add(obj)
        db.session.flush()

        reported_at = datetime(2026, 10, 27, 15, 0)
        act = ActionPlanActivity(
            plan_objective_id=obj.id, name="Apoyo jornada", deliverable="Listado",
            delivery_date=date(2026, 10, 26), lugar="Toro",
            reported_at=reported_at, reported_by_user_id=ids["editor"],
            evidence_url="https://drive/evid", description="Se capacitaron 30 personas",
            generates_report=True,
        )
        pending = ActionPlanActivity(
            plan_objective_id=obj.id, name="Sin reportar", deliverable="X",
            delivery_date=date(2026, 12, 1),
        )
        db.session.add_all([act, pending])
        db.session.flush()

        rep = Report(
            strategy_id=st.id, component_id=comp.id, report_date=date(2026, 10, 26),
            executive_summary="Resumen", intervention_location="Toro",
            zone_type=ZoneTypeEnum.URBANA, evidence_link="https://drive/evid",
            user_id=ids["editor"], action_plan_activity_id=act.id,
        )
        db.session.add(rep)
        db.session.flush()
        # Indicador ficticio: solo verificamos que el valor no cambie.
        db.session.add(ReportIndicatorValue(report_id=rep.id, indicator_id=76, value=30))
        db.session.commit()

        ids.update(activity=act.id, pending=pending.id, report=rep.id, plan=plan.id)

    tokens = {r: _login(client, f"ape-{r}@x.co", "pw")
              for r in ("admin", "monitor", "editor", "viewer", "admin2")}
    return ids, tokens


URL = "/action-plans/activities/{}/admin-edit"
NEW_NAME = "APOYO JORNADA VETERINARIA TORO"


def test_admin_renames_reported_activity_preserving_report(app, client, env):
    ids, tk = env
    resp = _put(client, URL.format(ids["activity"]), tk["admin"],
                {"name": NEW_NAME, "reason": "Corrección solicitada por el responsable"})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["activity"]["name"] == NEW_NAME
    assert body["activity"]["status"] == "Realizado"
    assert body["activity"]["linked_report_id"] == ids["report"]

    from app.modules.action_plans.models.action_plan import ActionPlanActivity, ActionPlanActivityChange
    from app.modules.indicators.models.Report.report import Report
    with app.app_context():
        act = ActionPlanActivity.query.get(ids["activity"])
        assert act.reported_at == datetime(2026, 10, 27, 15, 0)
        assert act.evidence_url == "https://drive/evid"
        assert act.description == "Se capacitaron 30 personas"
        assert act.generates_report is True
        assert act.computed_score == 7
        rep = Report.query.get(ids["report"])
        assert rep.action_plan_activity_id == ids["activity"]
        assert rep.report_date == date(2026, 10, 26)
        assert [(iv.indicator_id, float(iv.value)) for iv in rep.indicator_values] == [(76, 30.0)]

        changes = ActionPlanActivityChange.query.filter_by(activity_id=ids["activity"]).all()
        assert len(changes) == 1
        c = changes[0]
        assert (c.field, c.old_value, c.new_value) == ("name", "Apoyo jornada", NEW_NAME)
        assert c.user_id == ids["admin"]
        assert c.reason.startswith("Corrección")

    hist = client.get(f"/action-plans/activities/{ids['activity']}/changes", headers=_h(tk["monitor"]))
    assert hist.status_code == 200
    assert hist.get_json()[0]["new_value"] == NEW_NAME


@pytest.mark.parametrize("role", ["monitor", "editor", "viewer"])
def test_non_admin_roles_blocked(client, env, role):
    ids, tk = env
    resp = _put(client, URL.format(ids["activity"]), tk[role],
                {"name": "X nuevo", "reason": "intento no autorizado"})
    assert resp.status_code == 403


def test_monitor_with_permission_override_still_blocked(app, client, env):
    ids, _tk = env
    _add_override(app, ids["monitor"], PERM_ACTION_PLANS_EDIT_REPORTED, "grant")
    token = _login(client, "ape-monitor@x.co", "pw")  # token nuevo con el grant
    resp = _put(client, URL.format(ids["activity"]), token,
                {"name": "X nuevo", "reason": "monitor con override"})
    assert resp.status_code == 403


def test_admin_with_permission_revoked_blocked(app, client, env):
    ids, tk = env
    _add_override(app, ids["admin2"], PERM_ACTION_PLANS_EDIT_REPORTED, "revoke")
    # En tests el app_context es de sesión y comparte la sesión ORM entre
    # requests; en producción cada request abre sesión nueva. Expirar evita
    # leer la colección de overrides cacheada antes del revoke.
    from flask import g
    db.session.expire_all()
    for k in [k for k in vars(g) if k.startswith("_perm")]:
        delattr(g, k)
    # Token emitido ANTES de la revocación: igual queda bloqueado (se lee BD).
    resp = _put(client, URL.format(ids["activity"]), tk["admin2"],
                {"name": "X nuevo", "reason": "admin con permiso revocado"})
    assert resp.status_code == 403


def test_locked_fields_rejected(client, env):
    ids, tk = env
    for extra in ({"evidence_url": "https://otra"}, {"description": "cambiada"},
                  {"generates_report": False}, {"support_staff": []}, {"edit_all": True}):
        body = {"name": "Nombre nuevo", "reason": "motivo suficiente", **extra}
        resp = _put(client, URL.format(ids["activity"]), tk["admin"], body)
        assert resp.status_code == 422, extra


def test_reason_required(client, env):
    ids, tk = env
    assert _put(client, URL.format(ids["activity"]), tk["admin"], {"name": "Nombre nuevo"}).status_code == 422
    assert _put(client, URL.format(ids["activity"]), tk["admin"],
                {"name": "Nombre nuevo", "reason": "corto"}).status_code == 422


def test_no_changes_rejected(client, env):
    ids, tk = env
    resp = _put(client, URL.format(ids["activity"]), tk["admin"],
                {"name": "Apoyo jornada", "reason": "sin cambios reales"})
    assert resp.status_code == 422


def test_unreported_activity_not_allowed(client, env):
    ids, tk = env
    resp = _put(client, URL.format(ids["pending"]), tk["admin"],
                {"name": "Otro", "reason": "no está reportada"})
    assert resp.status_code == 409


@pytest.mark.parametrize("new_date,ok", [
    ("2026-10-20", True),    # antes del reporte, mismo año
    ("2026-10-28", False),   # posterior a la fecha de reporte (27-oct)
    ("2025-12-30", False),   # cambio de año
])
def test_delivery_date_rules(client, env, new_date, ok):
    ids, tk = env
    resp = _put(client, URL.format(ids["activity"]), tk["admin"],
                {"delivery_date": new_date, "reason": "fecha mal registrada"})
    assert (resp.status_code == 200) is ok, resp.get_data(as_text=True)
    if ok:
        # Fecha distinta a la del reporte vinculado → aviso, no bloqueo.
        assert resp.get_json()["warnings"]


def test_date_cannot_reopen_expired_evidence_window(app):
    from app.modules.action_plans.validators.action_plan_validator import ActionPlanValidator

    class Act:
        reported_at = datetime(2026, 10, 25, 10, 0)
        delivery_date = date(2026, 10, 1)
        evidence_url = None
        name = "a"; deliverable = "b"; lugar = None
        linked_report = None

    today = date(2026, 10, 30)  # plazo original (9-oct) vencido
    errors, _c, _w = ActionPlanValidator.validate_admin_edit(
        {"delivery_date": date(2026, 10, 24)}, Act(), today=today)
    assert "delivery_date" in errors
    # Mover a una fecha cuyo plazo también está vencido sí se permite.
    errors, changes, _w = ActionPlanValidator.validate_admin_edit(
        {"delivery_date": date(2026, 10, 5)}, Act(), today=today)
    assert not errors and "delivery_date" in changes


def test_regular_edit_endpoint_rejects_reported_activity(client, env):
    ids, tk = env
    resp = _put(client, f"/action-plans/activities/{ids['activity']}/edit", tk["admin"],
                {"name": "Por la puerta normal", "deliverable": "x"})
    assert resp.status_code == 409
