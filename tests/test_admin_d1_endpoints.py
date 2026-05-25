"""Tests del bloque admin RBAC, fase D1 (read-only).

Cubren los 4 endpoints nuevos:
- GET /permissions
- GET /roles/:role_id/permissions
- GET /users/:user_id/permissions
- GET /users/:user_id/permissions/overrides

Verifican autorización (admin/monitor/editor/viewer/sin auth), shape de
respuesta, edge cases 404 y semántica del cálculo de permisos efectivos
(role ∪ grants − revokes). También aseguran que llamar el endpoint para
un user_id distinto al actual no pisa el cache `flask.g` del current_user.
"""
import json

import pytest
from flask import g
from flask_jwt_extended import create_access_token

from app.core.extensions import db


# ─── Helpers de fixture ───────────────────────────────────────────────────


def _seed(app):
    from app.modules.indicators.commands.seed_permissions import seed_permissions
    result = app.test_cli_runner().invoke(seed_permissions)
    assert result.exit_code == 0, result.output


def _make_user(app, role_name, email, password="pw"):
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
    return resp.get_json()["access_token"]


def _token_for(client, app, role_name):
    """Crea usuario con rol y devuelve un access_token vía /auth/login."""
    email = f"d1-{role_name}@x.co"
    _make_user(app, role_name, email)
    return _login(client, email, "pw")


def _add_override(app, user_id, perm_code, effect, granted_by_id=None):
    """Inserta un UserPermission (grant/revoke) en la BD del test."""
    from app.shared.models.permission import Permission
    from app.shared.models.user_permission import UserPermission
    with app.app_context():
        perm = Permission.query.filter_by(code=perm_code).first()
        assert perm is not None, f"perm {perm_code} no existe"
        existing = UserPermission.query.filter_by(
            user_id=user_id, permission_id=perm.id
        ).first()
        if existing:
            existing.effect = effect
            existing.granted_by = granted_by_id
        else:
            db.session.add(UserPermission(
                user_id=user_id,
                permission_id=perm.id,
                effect=effect,
                granted_by=granted_by_id,
            ))
        db.session.commit()


# ═════════════════════════════════════════════════════════════════════════
# GET /permissions
# ═════════════════════════════════════════════════════════════════════════


def test_permissions_list_admin_ok(app, client):
    _seed(app)
    token = _token_for(client, app, "admin")
    resp = client.get("/permissions/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    # Coincide con el catálogo en cantidad.
    from app.shared.permissions.catalog import ALL_PERMISSIONS
    assert len(data) == len(ALL_PERMISSIONS)


def test_permissions_list_monitor_ok(app, client):
    _seed(app)
    token = _token_for(client, app, "monitor")
    resp = client.get("/permissions/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_permissions_list_editor_forbidden(app, client):
    _seed(app)
    token = _token_for(client, app, "editor")
    resp = client.get("/permissions/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_permissions_list_viewer_forbidden(app, client):
    _seed(app)
    token = _token_for(client, app, "viewer")
    resp = client.get("/permissions/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_permissions_list_no_auth_returns_401(app, client):
    _seed(app)
    resp = client.get("/permissions/")
    assert resp.status_code == 401


def test_permissions_list_shape_has_required_fields(app, client):
    _seed(app)
    token = _token_for(client, app, "admin")
    resp = client.get("/permissions/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.get_json()
    sample = data[0]
    assert {"code", "description", "module", "is_system"}.issubset(sample.keys())
    assert isinstance(sample["code"], str)
    assert isinstance(sample["is_system"], bool)


def test_permissions_list_sorted_by_module_then_code(app, client):
    _seed(app)
    token = _token_for(client, app, "admin")
    resp = client.get("/permissions/", headers={"Authorization": f"Bearer {token}"})
    data = resp.get_json()
    keys = [(p["module"], p["code"]) for p in data]
    assert keys == sorted(keys), "El catálogo debe venir ordenado por (module, code)"


def test_permissions_list_includes_new_users_read_permissions(app, client):
    """El permiso nuevo del D1 debe aparecer en el catálogo tras el seed."""
    _seed(app)
    token = _token_for(client, app, "admin")
    resp = client.get("/permissions/", headers={"Authorization": f"Bearer {token}"})
    codes = {p["code"] for p in resp.get_json()}
    assert "users.read_permissions" in codes


# ═════════════════════════════════════════════════════════════════════════
# GET /roles/:role_id/permissions
# ═════════════════════════════════════════════════════════════════════════


def _admin_role_id(app):
    from app.shared.models.role import Role
    with app.app_context():
        return Role.query.filter_by(name="admin").first().id


def test_role_permissions_admin_ok(app, client):
    _seed(app)
    role_id = _admin_role_id(app)
    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/roles/{role_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_role_permissions_monitor_ok(app, client):
    _seed(app)
    role_id = _admin_role_id(app)
    token = _token_for(client, app, "monitor")
    resp = client.get(
        f"/roles/{role_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_role_permissions_editor_forbidden(app, client):
    _seed(app)
    role_id = _admin_role_id(app)
    token = _token_for(client, app, "editor")
    resp = client.get(
        f"/roles/{role_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_role_permissions_viewer_forbidden(app, client):
    _seed(app)
    role_id = _admin_role_id(app)
    token = _token_for(client, app, "viewer")
    resp = client.get(
        f"/roles/{role_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_role_permissions_no_auth_returns_401(app, client):
    _seed(app)
    role_id = _admin_role_id(app)
    resp = client.get(f"/roles/{role_id}/permissions")
    assert resp.status_code == 401


def test_role_permissions_shape(app, client):
    _seed(app)
    role_id = _admin_role_id(app)
    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/roles/{role_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    payload = resp.get_json()
    assert "role" in payload
    assert "permissions" in payload
    # role detail tiene todos los campos esperados.
    role = payload["role"]
    assert {"id", "name", "description", "is_system",
            "permission_count", "user_count"}.issubset(role.keys())
    assert role["name"] == "admin"
    assert role["is_system"] is True
    assert isinstance(role["permission_count"], int)
    assert isinstance(role["user_count"], int)
    # permissions es lista con shape PermissionSchema.
    assert isinstance(payload["permissions"], list)
    if payload["permissions"]:
        p = payload["permissions"][0]
        assert {"code", "description", "module", "is_system"}.issubset(p.keys())


def test_role_permissions_admin_has_full_bundle(app, client):
    """admin debería tener todos los permisos del catálogo."""
    _seed(app)
    role_id = _admin_role_id(app)
    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/roles/{role_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    payload = resp.get_json()
    codes = {p["code"] for p in payload["permissions"]}
    from app.modules.indicators.commands.seed_permissions import BUNDLE_ADMIN
    assert codes == set(BUNDLE_ADMIN)
    assert payload["role"]["permission_count"] == len(BUNDLE_ADMIN)


def test_role_permissions_returns_404_for_unknown_role(app, client):
    _seed(app)
    token = _token_for(client, app, "admin")
    resp = client.get(
        "/roles/999999/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════════
# GET /users/:user_id/permissions
# ═════════════════════════════════════════════════════════════════════════


def test_user_permissions_admin_ok(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-target-editor@x.co")
    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/users/{target_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_user_permissions_monitor_forbidden(app, client):
    """Sólo admin puede ver permisos efectivos de OTROS usuarios."""
    _seed(app)
    target_id = _make_user(app, "editor", "d1-tgt-monitor@x.co")
    token = _token_for(client, app, "monitor")
    resp = client.get(
        f"/users/{target_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_user_permissions_editor_forbidden(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-tgt-editor@x.co")
    token = _token_for(client, app, "editor")
    resp = client.get(
        f"/users/{target_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_user_permissions_viewer_forbidden(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-tgt-viewer@x.co")
    token = _token_for(client, app, "viewer")
    resp = client.get(
        f"/users/{target_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_user_permissions_no_auth_returns_401(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-tgt-noauth@x.co")
    resp = client.get(f"/users/{target_id}/permissions")
    assert resp.status_code == 401


def test_user_permissions_returns_404_for_unknown_user(app, client):
    _seed(app)
    token = _token_for(client, app, "admin")
    resp = client.get(
        "/users/9999999/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_user_permissions_shape(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-tgt-shape@x.co")
    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/users/{target_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    payload = resp.get_json()
    assert {"user", "from_role", "grants", "revokes", "effective"}.issubset(payload.keys())
    assert {"id", "email", "role"}.issubset(payload["user"].keys())
    assert {"id", "name"}.issubset(payload["user"]["role"].keys())
    assert payload["user"]["id"] == target_id
    assert payload["user"]["role"]["name"] == "editor"
    for key in ("from_role", "grants", "revokes", "effective"):
        assert isinstance(payload[key], list)


def test_user_permissions_effective_equals_role_when_no_overrides(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-tgt-noov@x.co")
    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/users/{target_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    payload = resp.get_json()
    from app.modules.indicators.commands.seed_permissions import BUNDLE_EDITOR

    assert set(payload["from_role"]) == set(BUNDLE_EDITOR)
    assert payload["grants"] == []
    assert payload["revokes"] == []
    assert set(payload["effective"]) == set(BUNDLE_EDITOR)


def test_user_permissions_effective_applies_grant(app, client):
    _seed(app)
    target_id = _make_user(app, "viewer", "d1-tgt-grant@x.co")
    # viewer no tiene users.read_basic → se lo otorgamos.
    _add_override(app, target_id, "users.read_basic", "grant")

    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/users/{target_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    payload = resp.get_json()
    assert "users.read_basic" in payload["grants"]
    assert "users.read_basic" in payload["effective"]
    # El bundle base (reports.read) sigue ahí.
    assert "reports.read" in payload["effective"]


def test_user_permissions_effective_applies_revoke(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-tgt-revoke@x.co")
    # editor sí tiene reports.create — lo revocamos.
    _add_override(app, target_id, "reports.create", "revoke")

    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/users/{target_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    payload = resp.get_json()
    assert "reports.create" in payload["revokes"]
    assert "reports.create" not in payload["effective"]
    # El resto del bundle editor sigue.
    assert "reports.read" in payload["effective"]


def test_user_permissions_effective_formula_combines_grant_and_revoke(app, client):
    """effective = (from_role ∪ grants) − revokes."""
    _seed(app)
    target_id = _make_user(app, "viewer", "d1-tgt-combo@x.co")
    # viewer bundle = {reports.read}
    _add_override(app, target_id, "users.read_basic", "grant")  # +
    _add_override(app, target_id, "reports.read", "revoke")     # -

    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/users/{target_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    payload = resp.get_json()
    from_role = set(payload["from_role"])
    grants = set(payload["grants"])
    revokes = set(payload["revokes"])
    effective = set(payload["effective"])

    # Invariante semántica del modelo RBAC.
    assert effective == (from_role | grants) - revokes
    # En este caso:
    assert "users.read_basic" in effective  # grant añadido
    assert "reports.read" not in effective  # revocado


def test_user_permissions_does_not_pollute_current_user_cache(app, client):
    """Llamar /users/:other/permissions no debe pisar el cache del current_user.

    En modo test_request_context, el flask.g se comparte mientras el
    contexto está vivo. Verificamos que las claves `_perm_user_<id>`
    y `_perm_set_<id>` del current_user no se sobrescriban tras consultar
    el endpoint para OTRO usuario.
    """
    _seed(app)
    admin_id = _make_user(app, "admin", "d1-cache-admin@x.co")
    target_id = _make_user(app, "editor", "d1-cache-target@x.co")

    with app.app_context():
        token = create_access_token(identity=str(admin_id))

    # Pre-poblamos el cache del current_user simulando una request previa.
    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request()
        from app.utils.permissions import current_user, get_effective_permissions
        u = current_user()
        perms_before = set(get_effective_permissions(u))
        # Las claves `g._perm_set_<admin_id>` y `g._perm_user_<admin_id>` quedan seteadas.
        cached_user_obj = getattr(g, f"_perm_user_{admin_id}", None)
        cached_perms = getattr(g, f"_perm_set_{admin_id}", None)
        assert cached_user_obj is not None
        assert cached_perms == perms_before

    # Ahora, en una request al endpoint admin para target_id, los caches del
    # current_user no deben ser pisados por el lookup del target_id.
    resp = client.get(
        f"/users/{target_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Tras la request del endpoint, volvemos a verificar el cache del admin
    # en una nueva request: debe poder reconstruirse normalmente desde DB.
    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request()
        from app.utils.permissions import current_user, get_effective_permissions
        u = current_user()
        perms_after = set(get_effective_permissions(u))
        assert perms_after == perms_before, (
            "El cache de permisos del current_user fue alterado por la "
            "llamada al endpoint para otro usuario."
        )


def test_user_permissions_consecutive_calls_for_different_users(app, client):
    """Llamadas secuenciales a /users/X/permissions y /users/Y/permissions
    devuelven el set correcto de cada usuario (no se mezclan).
    """
    _seed(app)
    user_a = _make_user(app, "viewer", "d1-userA@x.co")
    user_b = _make_user(app, "editor", "d1-userB@x.co")
    token = _token_for(client, app, "admin")

    resp_a = client.get(
        f"/users/{user_a}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp_b = client.get(
        f"/users/{user_b}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    payload_a = resp_a.get_json()
    payload_b = resp_b.get_json()

    from app.modules.indicators.commands.seed_permissions import (
        BUNDLE_EDITOR, BUNDLE_VIEWER,
    )
    assert set(payload_a["effective"]) == set(BUNDLE_VIEWER)
    assert set(payload_b["effective"]) == set(BUNDLE_EDITOR)
    assert payload_a["user"]["id"] == user_a
    assert payload_b["user"]["id"] == user_b


# ═════════════════════════════════════════════════════════════════════════
# GET /users/:user_id/permissions/overrides
# ═════════════════════════════════════════════════════════════════════════


def test_user_overrides_admin_ok(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-ov-target@x.co")
    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/users/{target_id}/permissions/overrides",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_user_overrides_monitor_forbidden(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-ov-tgt-mon@x.co")
    token = _token_for(client, app, "monitor")
    resp = client.get(
        f"/users/{target_id}/permissions/overrides",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_user_overrides_editor_forbidden(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-ov-tgt-ed@x.co")
    token = _token_for(client, app, "editor")
    resp = client.get(
        f"/users/{target_id}/permissions/overrides",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_user_overrides_viewer_forbidden(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-ov-tgt-vw@x.co")
    token = _token_for(client, app, "viewer")
    resp = client.get(
        f"/users/{target_id}/permissions/overrides",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_user_overrides_no_auth_returns_401(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-ov-tgt-noauth@x.co")
    resp = client.get(f"/users/{target_id}/permissions/overrides")
    assert resp.status_code == 401


def test_user_overrides_returns_404_for_unknown_user(app, client):
    _seed(app)
    token = _token_for(client, app, "admin")
    resp = client.get(
        "/users/9999999/permissions/overrides",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


def test_user_overrides_empty_when_no_overrides(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d1-ov-empty@x.co")
    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/users/{target_id}/permissions/overrides",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_user_overrides_shape_with_grant_and_revoke(app, client):
    _seed(app)
    admin_id = _make_user(app, "admin", "d1-ov-actor@x.co")
    target_id = _make_user(app, "viewer", "d1-ov-with@x.co")
    _add_override(app, target_id, "users.read_basic", "grant", granted_by_id=admin_id)
    _add_override(app, target_id, "reports.read", "revoke", granted_by_id=admin_id)

    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/users/{target_id}/permissions/overrides",
        headers={"Authorization": f"Bearer {token}"},
    )
    payload = resp.get_json()
    assert len(payload) == 2
    sample = payload[0]
    assert {"permission", "effect", "granted_by", "granted_at"}.issubset(sample.keys())
    assert {"code", "description", "module"}.issubset(sample["permission"].keys())
    # granted_by debería tener id+email (no null) porque pasamos granted_by_id.
    assert sample["granted_by"] is not None
    assert sample["granted_by"]["id"] == admin_id
    assert sample["granted_by"]["email"] == "d1-ov-actor@x.co"
    # effect es "grant" o "revoke".
    effects = {row["effect"] for row in payload}
    assert effects == {"grant", "revoke"}


def test_user_overrides_granted_by_null_when_unknown(app, client):
    _seed(app)
    target_id = _make_user(app, "viewer", "d1-ov-noby@x.co")
    _add_override(app, target_id, "users.read_basic", "grant", granted_by_id=None)

    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/users/{target_id}/permissions/overrides",
        headers={"Authorization": f"Bearer {token}"},
    )
    payload = resp.get_json()
    assert len(payload) == 1
    assert payload[0]["granted_by"] is None


def test_user_overrides_ordered_by_module_then_code(app, client):
    _seed(app)
    target_id = _make_user(app, "viewer", "d1-ov-order@x.co")
    # Insertamos en orden NO alfabético para forzar el sort en el backend.
    _add_override(app, target_id, "users.read_basic", "grant")     # module=users
    _add_override(app, target_id, "audit.read",      "grant")      # module=audit
    _add_override(app, target_id, "reports.create",  "grant")      # module=reports
    _add_override(app, target_id, "reports.read",    "revoke")     # module=reports

    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/users/{target_id}/permissions/overrides",
        headers={"Authorization": f"Bearer {token}"},
    )
    payload = resp.get_json()
    keys = [(row["permission"]["module"], row["permission"]["code"]) for row in payload]
    assert keys == sorted(keys), f"esperaba orden por (module, code), recibí {keys}"
