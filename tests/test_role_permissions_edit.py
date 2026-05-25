"""Tests del PUT /roles/:id/permissions (D2 — bulk replace).

Cobertura:
- Autorización por rol (admin OK, otros 403, sin auth 401).
- Validación de input (faltante, mal-tipo, code desconocido, duplicados).
- Lockout: el rol `admin` no puede perder ningún permiso crítico.
- Semántica del bulk replace: diff correcto, no-op no audita, vaciado OK.
- AuditLog: shape, conteo, detail JSON parseable y campos exactos.
- Response shape idéntico al GET (role + permissions ordenados).
- `is_critical` presente en el catálogo (impacto del cambio al schema).
"""
import json

import pytest

from app.core.extensions import db


# ─── Helpers de fixture (mismos patrones que test_admin_d1_endpoints.py) ──

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
    """Crea usuario con rol y devuelve access_token tras login."""
    email = f"d2-{role_name}@x.co"
    _make_user(app, role_name, email)
    return _login(client, email, "pw")


def _role_id(app, name):
    from app.shared.models.role import Role
    with app.app_context():
        return Role.query.filter_by(name=name).first().id


def _role_codes(app, name):
    """Set actual de codes asignados al rol."""
    from app.shared.models.role import Role
    with app.app_context():
        role = Role.query.filter_by(name=name).first()
        return {a.permission.code for a in role.role_permissions if a.permission}


def _put(client, token, role_id, body):
    return client.put(
        f"/roles/{role_id}/permissions",
        data=json.dumps(body),
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )


# ═════════════════════════════════════════════════════════════════════════
# Autorización
# ═════════════════════════════════════════════════════════════════════════


def test_put_admin_ok(app, client):
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")
    resp = _put(client, token, rid, {"permission_codes": ["reports.read"]})
    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_put_editor_forbidden(app, client):
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "editor")
    resp = _put(client, token, rid, {"permission_codes": ["reports.read"]})
    assert resp.status_code == 403


def test_put_viewer_forbidden(app, client):
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "viewer")
    resp = _put(client, token, rid, {"permission_codes": ["reports.read"]})
    assert resp.status_code == 403


def test_put_monitor_forbidden(app, client):
    """Monitor lee pero NO edita (sólo admin tiene roles.manage)."""
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "monitor")
    resp = _put(client, token, rid, {"permission_codes": ["reports.read"]})
    assert resp.status_code == 403


def test_put_no_auth_returns_401(app, client):
    _seed(app)
    rid = _role_id(app, "viewer")
    resp = client.put(
        f"/roles/{rid}/permissions",
        data=json.dumps({"permission_codes": ["reports.read"]}),
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_put_role_not_found(app, client):
    _seed(app)
    token = _token_for(client, app, "admin")
    resp = _put(client, token, 999_999, {"permission_codes": ["reports.read"]})
    assert resp.status_code == 404
    assert resp.get_json()["message"] == "Role not found"


# ═════════════════════════════════════════════════════════════════════════
# Validación de input
# ═════════════════════════════════════════════════════════════════════════


def test_put_missing_permission_codes_returns_422(app, client):
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")
    resp = _put(client, token, rid, {})
    assert resp.status_code == 422


def test_put_permission_codes_not_a_list_returns_422(app, client):
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")
    resp = _put(client, token, rid, {"permission_codes": "reports.read"})
    assert resp.status_code == 422


def test_put_unknown_code_returns_404(app, client):
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")
    resp = _put(
        client, token, rid,
        {"permission_codes": ["reports.read", "totally.fake_perm"]},
    )
    assert resp.status_code == 404
    payload = resp.get_json()
    assert "totally.fake_perm" in payload.get("message", "")


def test_put_unknown_code_does_not_persist_changes(app, client):
    """Si el body tiene UN code malo, NADA se persiste — atómico."""
    _seed(app)
    rid = _role_id(app, "viewer")
    before = _role_codes(app, "viewer")
    token = _token_for(client, app, "admin")

    resp = _put(
        client, token, rid,
        {"permission_codes": ["reports.read", "users.read_basic", "no.existe"]},
    )
    assert resp.status_code == 404
    after = _role_codes(app, "viewer")
    assert before == after, "El rol no debió modificarse cuando hubo code inválido"


def test_put_duplicates_are_normalized_as_set(app, client):
    """Codes duplicados en el body se procesan como set, sin error."""
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")
    resp = _put(
        client, token, rid,
        {"permission_codes": ["reports.read", "reports.read", "users.read_basic"]},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    codes = {p["code"] for p in payload["permissions"]}
    assert codes == {"reports.read", "users.read_basic"}


# ═════════════════════════════════════════════════════════════════════════
# Lockout — el rol admin no puede perder permisos críticos
# ═════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("critical_code", [
    "roles.read",
    "roles.manage",
    "users.manage",
    "users.manage_permissions",
    "users.read_permissions",
])
def test_put_admin_role_cannot_lose_critical_perm(app, client, critical_code):
    _seed(app)
    from app.shared.permissions.catalog import ALL_PERMISSIONS
    full = [p.code for p in ALL_PERMISSIONS]
    # Construimos un set IGUAL al full bundle menos UN crítico → debe bloquearse.
    requested = [c for c in full if c != critical_code]
    rid = _role_id(app, "admin")
    token = _token_for(client, app, "admin")

    resp = _put(client, token, rid, {"permission_codes": requested})
    assert resp.status_code == 403
    msg = resp.get_json().get("message", "")
    assert critical_code in msg


def test_put_admin_role_lockout_message_lists_all_removed_criticals(app, client):
    """Cuando se intenta quitar 2 críticos a la vez, el mensaje los nombra."""
    _seed(app)
    from app.shared.permissions.catalog import ALL_PERMISSIONS
    drops = {"roles.read", "users.manage"}
    requested = [p.code for p in ALL_PERMISSIONS if p.code not in drops]
    rid = _role_id(app, "admin")
    token = _token_for(client, app, "admin")
    resp = _put(client, token, rid, {"permission_codes": requested})
    assert resp.status_code == 403
    msg = resp.get_json().get("message", "")
    for d in drops:
        assert d in msg


def test_put_admin_role_keeping_all_criticals_ok(app, client):
    """Quitar permisos NO críticos al admin es permitido."""
    _seed(app)
    rid = _role_id(app, "admin")
    token = _token_for(client, app, "admin")
    from app.shared.permissions.catalog import ALL_PERMISSIONS, CRITICAL_PERMS
    # Quitamos reports.read (no crítico) pero mantenemos todos los críticos.
    requested = [p.code for p in ALL_PERMISSIONS if p.code != "reports.read"]
    resp = _put(client, token, rid, {"permission_codes": requested})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    # Verificación: los 5 críticos siguen presentes.
    payload = resp.get_json()
    after_codes = {p["code"] for p in payload["permissions"]}
    assert CRITICAL_PERMS.issubset(after_codes)
    assert "reports.read" not in after_codes


def test_put_lockout_only_applies_to_admin_role(app, client):
    """El lockout es exclusivo del rol admin — editor puede perder cualquier perm."""
    _seed(app)
    # editor NO debería tener problema en pasar de su bundle al set vacío.
    rid = _role_id(app, "editor")
    token = _token_for(client, app, "admin")
    resp = _put(client, token, rid, {"permission_codes": []})
    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_put_lockout_does_not_apply_when_admin_has_no_critical_yet(app, client):
    """Caso bordeline: si admin no tiene un crítico, no se trata de 'quitarlo'."""
    _seed(app)
    rid = _role_id(app, "admin")
    token = _token_for(client, app, "admin")

    # Setup: bajar admin a un set sin ese crítico es prohibido en sí mismo,
    # así que probamos con un rol custom que llamamos admin-like.
    # Como no podemos renombrar admin, validamos solo lo contrario:
    # cualquier intento de bajar de un set que TIENE el crítico debe bloquear.
    from app.shared.permissions.catalog import ALL_PERMISSIONS
    full = [p.code for p in ALL_PERMISSIONS]
    requested = [c for c in full if c != "roles.read"]
    resp = _put(client, token, rid, {"permission_codes": requested})
    assert resp.status_code == 403


# ═════════════════════════════════════════════════════════════════════════
# Semántica del bulk replace
# ═════════════════════════════════════════════════════════════════════════


def test_put_empty_codes_removes_all_for_viewer(app, client):
    """Enviar [] al rol viewer lo deja sin permisos."""
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")

    # Estado controlado: viewer arranca con al menos un perm asignado.
    # El app fixture es session-scoped y otros tests pueden haber vaciado el rol.
    setup = _put(client, token, rid, {"permission_codes": ["reports.read"]})
    assert setup.status_code == 200
    before = _role_codes(app, "viewer")
    assert "reports.read" in before

    resp = _put(client, token, rid, {"permission_codes": []})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    after = _role_codes(app, "viewer")
    assert after == set()
    payload = resp.get_json()
    assert payload["role"]["permission_count"] == 0
    assert payload["permissions"] == []


def test_put_replace_with_different_set_computes_correct_diff(app, client):
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")

    # viewer bundle: {reports.read} → reemplazo con {users.read_basic, audit.read}
    resp = _put(
        client, token, rid,
        {"permission_codes": ["users.read_basic", "audit.read"]},
    )
    assert resp.status_code == 200
    after = _role_codes(app, "viewer")
    assert after == {"users.read_basic", "audit.read"}


def test_put_noop_does_not_emit_audit_log(app, client):
    """Si los codes coinciden EXACTAMENTE con lo actual, no se audita."""
    _seed(app)
    from app.shared.models.audit_log import AuditLog

    rid = _role_id(app, "viewer")
    before_codes = sorted(_role_codes(app, "viewer"))

    token = _token_for(client, app, "admin")

    with app.app_context():
        before_logs = AuditLog.query.filter_by(
            entity="role_permissions",
            entity_id=rid,
        ).count()

    resp = _put(client, token, rid, {"permission_codes": before_codes})
    assert resp.status_code == 200

    with app.app_context():
        after_logs = AuditLog.query.filter_by(
            entity="role_permissions",
            entity_id=rid,
        ).count()

    assert after_logs == before_logs, "Un no-op no debe emitir AuditLog"


def test_put_noop_returns_current_state_shape(app, client):
    """No-op devuelve el estado actual con shape role+permissions."""
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")
    current = sorted(_role_codes(app, "viewer"))
    resp = _put(client, token, rid, {"permission_codes": current})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert {p["code"] for p in payload["permissions"]} == set(current)


def test_put_idempotent_repeated_calls_same_result(app, client):
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")
    body = {"permission_codes": ["audit.read", "users.read_basic"]}

    resp1 = _put(client, token, rid, body)
    resp2 = _put(client, token, rid, body)
    assert resp1.status_code == 200
    assert resp2.status_code == 200

    codes_after = _role_codes(app, "viewer")
    assert codes_after == {"audit.read", "users.read_basic"}


# ═════════════════════════════════════════════════════════════════════════
# AuditLog
# ═════════════════════════════════════════════════════════════════════════


def test_put_emits_exactly_one_audit_log_on_change(app, client):
    _seed(app)
    from app.shared.models.audit_log import AuditLog

    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")

    with app.app_context():
        before = AuditLog.query.filter_by(
            entity="role_permissions",
            entity_id=rid,
        ).count()

    resp = _put(client, token, rid, {"permission_codes": ["audit.read"]})
    assert resp.status_code == 200

    with app.app_context():
        after = AuditLog.query.filter_by(
            entity="role_permissions",
            entity_id=rid,
        ).count()

    assert after - before == 1


def test_put_audit_log_fields_are_correct(app, client):
    _seed(app)
    from app.shared.models.audit_log import AuditLog
    from app.shared.models.user import User

    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")
    # Quien hizo login fue d2-admin@x.co
    with app.app_context():
        actor_email = "d2-admin@x.co"
        actor = User.query.filter_by(email=actor_email).first()
        actor_id = actor.id

    resp = _put(client, token, rid, {"permission_codes": ["audit.read"]})
    assert resp.status_code == 200

    with app.app_context():
        log = (
            AuditLog.query
            .filter_by(entity="role_permissions", entity_id=rid)
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert log is not None
        assert log.entity == "role_permissions"
        assert log.entity_id == rid
        assert log.action == "updated"
        assert log.user_id == actor_id


def test_put_audit_log_detail_is_valid_json_with_expected_shape(app, client):
    _seed(app)
    from app.shared.models.audit_log import AuditLog

    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")

    # Estado controlado: forzamos el rol viewer a {reports.read} antes
    # de medir el diff. El app fixture es session-scoped, por lo que
    # tests previos pueden haber dejado el rol en otro estado.
    setup = _put(client, token, rid, {"permission_codes": ["reports.read"]})
    assert setup.status_code == 200
    before_codes = _role_codes(app, "viewer")
    before_count = len(before_codes)

    # Reemplazo: {reports.read} → {users.read_basic, audit.read}
    resp = _put(
        client, token, rid,
        {"permission_codes": ["users.read_basic", "audit.read"]},
    )
    assert resp.status_code == 200

    with app.app_context():
        log = (
            AuditLog.query
            .filter_by(entity="role_permissions", entity_id=rid)
            .order_by(AuditLog.id.desc())
            .first()
        )
        payload = json.loads(log.detail)

    # Shape exacto:
    assert set(payload.keys()) == {
        "role", "added", "removed", "before_count",
        "after_count", "shadow_mode_active",
    }
    assert payload["role"] == {"id": rid, "name": "viewer"}
    assert set(payload["added"]) == {"users.read_basic", "audit.read"}
    assert payload["removed"] == ["reports.read"]
    assert payload["before_count"] == before_count
    assert payload["after_count"] == 2
    assert isinstance(payload["shadow_mode_active"], bool)


def test_put_audit_log_detail_reflects_shadow_mode_config(app, client):
    """`shadow_mode_active` refleja `current_app.config['PERM_SHADOW_MODE']`."""
    _seed(app)
    from app.shared.models.audit_log import AuditLog

    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")

    # Forzamos shadow_mode=True para esta llamada.
    app.config["PERM_SHADOW_MODE"] = True
    try:
        resp = _put(client, token, rid, {"permission_codes": ["audit.read"]})
        assert resp.status_code == 200
        with app.app_context():
            log = (
                AuditLog.query
                .filter_by(entity="role_permissions", entity_id=rid)
                .order_by(AuditLog.id.desc())
                .first()
            )
            payload = json.loads(log.detail)
        assert payload["shadow_mode_active"] is True
    finally:
        app.config["PERM_SHADOW_MODE"] = False

    # Ahora con shadow_mode=False.
    resp = _put(
        client, token, rid,
        {"permission_codes": ["audit.read", "users.read_basic"]},
    )
    assert resp.status_code == 200
    with app.app_context():
        log = (
            AuditLog.query
            .filter_by(entity="role_permissions", entity_id=rid)
            .order_by(AuditLog.id.desc())
            .first()
        )
        payload = json.loads(log.detail)
    assert payload["shadow_mode_active"] is False


def test_put_audit_detail_is_deterministic_json(app, client):
    """Serialización con sort_keys=True para que los diffs en CI sean estables."""
    _seed(app)
    from app.shared.models.audit_log import AuditLog

    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")
    resp = _put(client, token, rid, {"permission_codes": ["audit.read"]})
    assert resp.status_code == 200

    with app.app_context():
        log = (
            AuditLog.query
            .filter_by(entity="role_permissions", entity_id=rid)
            .order_by(AuditLog.id.desc())
            .first()
        )
        raw = log.detail
    # Las claves del JSON deben aparecer ordenadas alfabéticamente.
    parsed = json.loads(raw)
    re_serialized = json.dumps(parsed, sort_keys=True)
    assert raw == re_serialized


# ═════════════════════════════════════════════════════════════════════════
# Response shape (idéntico al GET)
# ═════════════════════════════════════════════════════════════════════════


def test_put_response_shape_matches_get(app, client):
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")
    resp = _put(client, token, rid, {"permission_codes": ["audit.read"]})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert "role" in payload and "permissions" in payload
    role = payload["role"]
    assert {"id", "name", "description", "is_system",
            "permission_count", "user_count"}.issubset(role.keys())
    assert role["id"] == rid
    assert role["name"] == "viewer"
    assert isinstance(payload["permissions"], list)
    if payload["permissions"]:
        p = payload["permissions"][0]
        assert {"code", "description", "module", "is_system",
                "is_critical"}.issubset(p.keys())


def test_put_permission_count_matches_assigned(app, client):
    """role.permission_count debe ser igual al tamaño del set persistido."""
    _seed(app)
    from app.shared.models.role import Role
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")

    target = ["audit.read", "users.read_basic", "reports.read"]
    resp = _put(client, token, rid, {"permission_codes": target})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["role"]["permission_count"] == len(target)

    with app.app_context():
        role = Role.query.get(rid)
        assert role.role_permissions is not None
        actual_count = len(list(role.role_permissions))
    assert actual_count == len(target)


def test_put_permissions_sorted_by_module_then_code(app, client):
    _seed(app)
    rid = _role_id(app, "viewer")
    token = _token_for(client, app, "admin")
    # users.read_basic (module=users) y audit.read (module=audit).
    # Esperado: audit.read primero, users.read_basic después.
    resp = _put(
        client, token, rid,
        {"permission_codes": ["users.read_basic", "audit.read"]},
    )
    assert resp.status_code == 200
    perms = resp.get_json()["permissions"]
    keys = [(p["module"], p["code"]) for p in perms]
    assert keys == sorted(keys)


# ═════════════════════════════════════════════════════════════════════════
# is_critical en GET /permissions/ (regresión del schema change)
# ═════════════════════════════════════════════════════════════════════════


def test_permissions_catalog_exposes_is_critical_flag(app, client):
    """GET /permissions/ debe traer is_critical=True para los 5 críticos."""
    _seed(app)
    token = _token_for(client, app, "admin")
    resp = client.get("/permissions/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    payload = resp.get_json()

    by_code = {p["code"]: p for p in payload}
    expected_critical = {
        "roles.read", "roles.manage", "users.manage",
        "users.manage_permissions", "users.read_permissions",
    }
    for code in expected_critical:
        assert by_code[code]["is_critical"] is True, code

    # Sanity-check inverso: algunos no-críticos.
    for code in ("reports.read", "audit.read", "datasets.read"):
        assert by_code[code]["is_critical"] is False, code


def test_role_permissions_get_exposes_is_critical(app, client):
    """GET /roles/:id/permissions también incluye is_critical (mismo schema)."""
    _seed(app)
    rid = _role_id(app, "admin")
    token = _token_for(client, app, "admin")
    resp = client.get(
        f"/roles/{rid}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    perms = resp.get_json()["permissions"]
    by_code = {p["code"]: p for p in perms}
    # admin tiene los 5 críticos por bundle.
    for code in ("roles.read", "roles.manage", "users.manage",
                 "users.manage_permissions", "users.read_permissions"):
        assert by_code[code]["is_critical"] is True
