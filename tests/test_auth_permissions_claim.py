"""Tests del Bloque 6 — JWT claim `permissions` + UserSchema.permissions.

Verifican:
- Login emite el claim `permissions` en el access token.
- Login response.user.permissions trae el set efectivo del usuario.
- Refresh re-emite el claim.
- /users/me incluye permissions para el usuario activo.
- /users/ list devuelve `permissions: null` para otros usuarios (no leak).
- JWT viejo SIN claim sigue siendo aceptado por endpoints actuales (compat).
- Tamaño del JWT razonable (smoke).
"""
import json

import jwt as pyjwt
import pytest

from app.core.extensions import db


def _seed(app):
    from app.modules.indicators.commands.seed_permissions import seed_permissions
    runner = app.test_cli_runner()
    result = runner.invoke(seed_permissions)
    assert result.exit_code == 0, result.output


def _create_user(app, role_name: str, email: str, password: str = "pw"):
    from app.shared.models.user import User
    from app.shared.models.role import Role
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        u = User.query.filter_by(email=email).first()
        if u is None:
            u = User(first_name="T", last_name="T", email=email, role_id=role.id)
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
        return u.id


def _login(client, email, password):
    resp = client.post(
        "/auth/login",
        data=json.dumps({"email": email, "password": password}),
        content_type="application/json",
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()


# ─── 1) Login emite el claim ──────────────────────────────────────────────

def test_login_emits_permissions_claim_in_access_token(app, client):
    _seed(app)
    _create_user(app, "admin", "admin-b6@x.co", "pw")

    body = _login(client, "admin-b6@x.co", "pw")
    decoded = pyjwt.decode(body["access_token"], options={"verify_signature": False})
    assert "permissions" in decoded
    assert isinstance(decoded["permissions"], list)
    # admin trae los 30 codes del bundle.
    from app.shared.permissions.catalog import ALL_PERMISSIONS
    assert set(decoded["permissions"]) == {p.code for p in ALL_PERMISSIONS}


def test_login_response_user_has_permissions_field(app, client):
    _seed(app)
    _create_user(app, "viewer", "viewer-b6@x.co", "pw")

    body = _login(client, "viewer-b6@x.co", "pw")
    user_dump = body["user"]
    assert "permissions" in user_dump
    assert isinstance(user_dump["permissions"], list)
    # Bundle viewer = {reports.read}.
    assert set(user_dump["permissions"]) == {"reports.read"}


# ─── 2) Refresh re-emite el claim ─────────────────────────────────────────

def test_refresh_emits_permissions_claim(app, client):
    _seed(app)
    _create_user(app, "editor", "editor-b6@x.co", "pw")

    body = _login(client, "editor-b6@x.co", "pw")
    refresh = body["refresh_token"]

    resp = client.post(
        "/auth/refresh",
        headers={"Authorization": f"Bearer {refresh}"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    new_access = resp.get_json()["access_token"]
    decoded = pyjwt.decode(new_access, options={"verify_signature": False})
    assert "permissions" in decoded
    from app.modules.indicators.commands.seed_permissions import BUNDLE_EDITOR
    assert set(decoded["permissions"]) == set(BUNDLE_EDITOR)


# ─── 3) /users/me incluye permissions ─────────────────────────────────────

def test_users_me_includes_permissions_for_current_user(app, client):
    _seed(app)
    _create_user(app, "monitor", "monitor-b6@x.co", "pw")

    body = _login(client, "monitor-b6@x.co", "pw")
    access = body["access_token"]

    resp = client.get("/users/me", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    payload = resp.get_json()
    assert "permissions" in payload
    from app.modules.indicators.commands.seed_permissions import BUNDLE_MONITOR
    assert set(payload["permissions"]) == set(BUNDLE_MONITOR)


# ─── 4) /users/ list NO filtra permisos de otros usuarios ─────────────────

def test_users_list_does_not_leak_permissions_of_other_users(app, client):
    _seed(app)
    _create_user(app, "admin", "admin-list@x.co", "pw")
    _create_user(app, "editor", "editor-other@x.co", "pw")

    body = _login(client, "admin-list@x.co", "pw")
    access = body["access_token"]

    resp = client.get("/users/", headers={"Authorization": f"Bearer {access}"})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    users = resp.get_json()
    assert isinstance(users, list)
    me = [u for u in users if u.get("email") == "admin-list@x.co"][0]
    other = [u for u in users if u.get("email") == "editor-other@x.co"][0]
    # El propio usuario sí trae sus permisos.
    assert isinstance(me["permissions"], list)
    assert len(me["permissions"]) > 0
    # Otros usuarios: permissions=None / null. NO se filtran permisos ajenos.
    assert other.get("permissions") is None


# ─── 5) Compat: JWT viejo sin claim sigue funcionando ─────────────────────

def test_legacy_jwt_without_permissions_claim_still_works(app, client):
    _seed(app)
    uid = _create_user(app, "viewer", "viewer-legacy-b6@x.co", "pw")

    from flask_jwt_extended import create_access_token
    with app.app_context():
        # JWT estilo "antes del Bloque 6" — sin claim permissions.
        legacy_token = create_access_token(identity=str(uid))

    # /users/me debe seguir respondiendo 200 con el viewer.
    resp = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {legacy_token}"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    payload = resp.get_json()
    # Permissions se computan vía fallback BD.
    assert isinstance(payload.get("permissions"), list)
    assert "reports.read" in payload["permissions"]


# ─── 6) Tamaño del JWT razonable ──────────────────────────────────────────

def test_jwt_payload_size_remains_reasonable(app, client):
    """Sanity check: admin (30 codes) en JWT no debe exceder 2KB."""
    _seed(app)
    _create_user(app, "admin", "admin-size@x.co", "pw")

    body = _login(client, "admin-size@x.co", "pw")
    token = body["access_token"]
    # JWT base64-encoded. Tamaño de la representación textual.
    assert len(token) < 2048, f"JWT muy grande: {len(token)} bytes"


# ─── 7) Smoke: respuestas existentes siguen iguales (excepto el campo nuevo) ─

def test_login_response_shape_preserves_legacy_keys(app, client):
    _seed(app)
    _create_user(app, "editor", "editor-shape@x.co", "pw")

    body = _login(client, "editor-shape@x.co", "pw")
    assert set(body.keys()) == {"access_token", "refresh_token", "user"}
    # `user` debe seguir teniendo TODAS las llaves históricas + permissions.
    expected_min = {
        "id", "first_name", "last_name", "email",
        "is_active", "created_at", "updated_at",
        "role", "component_assignments",
        # Nueva:
        "permissions",
    }
    assert expected_min.issubset(set(body["user"].keys()))
