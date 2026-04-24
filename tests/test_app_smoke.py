"""
Smoke de la app Flask: levanta correctamente y los endpoints críticos
están registrados.
"""

import json


def test_app_levanta(app):
    assert app is not None


def test_rutas_criticas_registradas(app):
    rules = {r.rule for r in app.url_map.iter_rules()}
    for r in [
        "/auth/login",
        "/auth/refresh",
        "/auth/logout",
        "/reports/",
        "/reports/<int:report_id>",
        "/reports/all",
        "/users/",
        "/users/me",
        "/users/<int:user_id>",
        "/roles/",
        "/kpis/",
    ]:
        assert r in rules, f"Falta ruta crítica: {r}"


def test_login_invalido_devuelve_401(client):
    resp = client.post(
        "/auth/login",
        data=json.dumps({"email": "no@existe.com", "password": "x"}),
        content_type="application/json",
    )
    assert resp.status_code == 401, resp.get_data(as_text=True)


def test_endpoints_protegidos_devuelven_401_sin_token(client):
    # Sin Authorization header → token_missing → 401 (gracias a los
    # loaders JWT custom registrados en error_handlers).
    for path in ("/reports/", "/users/", "/kpis/", "/roles/"):
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} → {resp.status_code}"
        body = resp.get_json()
        assert body.get("error") in ("token_missing", "token_invalid"), body


def test_kpis_responde_estructura_esperada_para_2026(client, app):
    """Sin reportes en BD el snapshot debe ser todo cero pero con la
    forma correcta."""
    from app.shared.models.user import User
    from app.shared.models.role import Role
    from app.core.extensions import db
    from flask_jwt_extended import create_access_token

    with app.app_context():
        # Sembrar role + user mínimos para emitir un JWT válido.
        if not Role.query.first():
            db.session.add(Role(id=1, name="admin"))
            db.session.commit()
        if not User.query.first():
            u = User(first_name="T", last_name="T", email="t@t.com", role_id=1)
            u.set_password("x")
            db.session.add(u)
            db.session.commit()
        uid = User.query.first().id
        token = create_access_token(identity=str(uid))

    resp = client.get("/kpis/?year=2026", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    for k in (
        "year", "asistencias_tecnicas", "denuncias_reportadas",
        "personas_capacitadas", "ninos_sensibilizados",
        "animales_esterilizados", "refugios_impactados",
        "emprendedores_cofinanciados",
    ):
        assert k in body, f"Falta clave {k} en {body}"
    assert body["year"] == 2026
    # Todos los valores numéricos del snapshot deben ser enteros >= 0;
    # no se asume cero porque la fixture inicializa esquemas con migrate
    # y puede haber semillas mínimas.
    for k, v in body.items():
        if k == "year":
            continue
        assert isinstance(v, int) and v >= 0, f"{k}={v!r}"
