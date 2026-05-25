"""Tests del Bloque 7 — GET /users/me/permissions."""
import json

from app.core.extensions import db


def _seed(app):
    from app.modules.indicators.commands.seed_permissions import seed_permissions
    result = app.test_cli_runner().invoke(seed_permissions)
    assert result.exit_code == 0, result.output


def _create_user(app, role_name, email, password="pw"):
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


def test_endpoint_returns_role_and_permissions_for_current_user(app, client):
    _seed(app)
    _create_user(app, "monitor", "monitor-me-perm@x.co", "pw")

    body = _login(client, "monitor-me-perm@x.co", "pw")
    access = body["access_token"]

    resp = client.get(
        "/users/me/permissions",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    payload = resp.get_json()
    assert payload["role"]["name"] == "monitor"
    assert isinstance(payload["permissions"], list)
    from app.modules.indicators.commands.seed_permissions import BUNDLE_MONITOR
    assert set(payload["permissions"]) == set(BUNDLE_MONITOR)


def test_endpoint_requires_jwt(app, client):
    resp = client.get("/users/me/permissions")
    assert resp.status_code == 401, resp.get_data(as_text=True)


def test_endpoint_works_with_legacy_jwt_without_claim(app, client):
    """JWT viejo sin claim 'permissions' → fallback BD computa el set."""
    _seed(app)
    uid = _create_user(app, "editor", "editor-legacy-mep@x.co", "pw")

    from flask_jwt_extended import create_access_token
    with app.app_context():
        token = create_access_token(identity=str(uid))

    resp = client.get(
        "/users/me/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    payload = resp.get_json()
    from app.modules.indicators.commands.seed_permissions import BUNDLE_EDITOR
    assert set(payload["permissions"]) == set(BUNDLE_EDITOR)
