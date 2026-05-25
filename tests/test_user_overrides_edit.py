"""Tests del PUT /users/:id/permissions/overrides (D3 — bulk replace).

Cobertura:
- Autorización por rol/permiso (admin OK, otros 403, sin auth 401).
- Validación de input (missing, mal-tipo, code desconocido, effect malo,
  duplicados, revoke huérfano).
- Lockouts:
  - Self-lockout: admin no puede revocarse a sí mismo críticos.
  - Main-admin lockout: nadie puede revocar críticos al main admin.
  - Admin colectivo: nadie puede revocar críticos a otros admins.
  - Positivo: grant de crítico permitido; revoke no-crítico permitido.
- Bulk replace semantics: vaciar quita todo, grant→revoke audita changed,
  no-op sin audit, idempotencia.
- AuditLog: shape exacto, JSON parseable, sort_keys, shadow_mode flag.
- Cache invalidation: tras PUT, el set efectivo refleja el cambio.
- Response shape: {overrides, permissions} con effective recalculado.
"""
import json

import pytest

from app.core.extensions import db


# ─── Helpers (mismo patrón que test_admin_d1_endpoints.py / D2) ───────────


def _seed(app):
    from app.modules.indicators.commands.seed_permissions import seed_permissions
    result = app.test_cli_runner().invoke(seed_permissions)
    assert result.exit_code == 0, result.output


def _make_user(app, role_name, email, password="pw", is_main_admin=False):
    from app.shared.models.user import User
    from app.shared.models.role import Role
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        u = User.query.filter_by(email=email).first()
        if u is None:
            u = User(
                first_name="T", last_name="T", email=email,
                role_id=role.id, is_main_admin=is_main_admin,
            )
            u.set_password(password)
            db.session.add(u)
            db.session.commit()
        elif u.is_main_admin != is_main_admin:
            u.is_main_admin = is_main_admin
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


def _token_for(client, app, role_name, email_suffix=""):
    """Crea usuario con rol y devuelve access_token."""
    suffix = f"-{email_suffix}" if email_suffix else ""
    email = f"d3-{role_name}{suffix}@x.co"
    _make_user(app, role_name, email)
    return _login(client, email, "pw")


def _put(client, token, user_id, body):
    return client.put(
        f"/users/{user_id}/permissions/overrides",
        data=json.dumps(body),
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )


def _clear_overrides(app, user_id):
    """Helper: vacía los overrides del usuario en BD (para aislamiento)."""
    from app.shared.models.user_permission import UserPermission
    with app.app_context():
        UserPermission.query.filter_by(user_id=user_id).delete()
        db.session.commit()


def _overrides_of(app, user_id):
    """Devuelve set de (code, effect) de los overrides actuales del usuario."""
    from app.shared.models.user_permission import UserPermission
    with app.app_context():
        rows = UserPermission.query.filter_by(user_id=user_id).all()
        return {(ov.permission.code, ov.effect) for ov in rows}


# ═════════════════════════════════════════════════════════════════════════
# Autorización
# ═════════════════════════════════════════════════════════════════════════


def test_put_admin_ok(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d3-tgt-ok@x.co")
    _clear_overrides(app, target_id)
    token = _token_for(client, app, "admin")
    resp = _put(client, token, target_id, {"overrides": []})
    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_put_editor_forbidden(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d3-tgt-ed-403@x.co")
    token = _token_for(client, app, "editor")
    resp = _put(client, token, target_id, {"overrides": []})
    assert resp.status_code == 403


def test_put_viewer_forbidden(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d3-tgt-vw-403@x.co")
    token = _token_for(client, app, "viewer")
    resp = _put(client, token, target_id, {"overrides": []})
    assert resp.status_code == 403


def test_put_monitor_forbidden(app, client):
    """Monitor lee pero NO edita overrides (solo admin tiene
    users.manage_permissions)."""
    _seed(app)
    target_id = _make_user(app, "editor", "d3-tgt-mon-403@x.co")
    token = _token_for(client, app, "monitor")
    resp = _put(client, token, target_id, {"overrides": []})
    assert resp.status_code == 403


def test_put_no_auth_returns_401(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d3-tgt-noauth@x.co")
    resp = client.put(
        f"/users/{target_id}/permissions/overrides",
        data=json.dumps({"overrides": []}),
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_put_user_not_found(app, client):
    _seed(app)
    token = _token_for(client, app, "admin")
    resp = _put(client, token, 9_999_999, {"overrides": []})
    assert resp.status_code == 404
    assert resp.get_json()["message"] == "User not found"


# ═════════════════════════════════════════════════════════════════════════
# Validación de input
# ═════════════════════════════════════════════════════════════════════════


def test_put_missing_overrides_returns_422(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d3-val-miss@x.co")
    token = _token_for(client, app, "admin")
    resp = _put(client, token, target_id, {})
    assert resp.status_code == 422


def test_put_overrides_not_a_list_returns_422(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d3-val-notlist@x.co")
    token = _token_for(client, app, "admin")
    resp = _put(client, token, target_id, {"overrides": "no es lista"})
    assert resp.status_code == 422


def test_put_invalid_effect_returns_422(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d3-val-effect@x.co")
    token = _token_for(client, app, "admin")
    resp = _put(client, token, target_id, {
        "overrides": [{"permission_code": "audit.read", "effect": "MAYBE"}],
    })
    assert resp.status_code == 422


def test_put_duplicate_permission_code_returns_422(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d3-val-dup@x.co")
    token = _token_for(client, app, "admin")
    resp = _put(client, token, target_id, {
        "overrides": [
            {"permission_code": "audit.read", "effect": "grant"},
            {"permission_code": "audit.read", "effect": "revoke"},
        ],
    })
    assert resp.status_code == 422
    msg = resp.get_json().get("message", "")
    assert "audit.read" in msg


def test_put_unknown_permission_code_returns_404(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d3-val-unk@x.co")
    token = _token_for(client, app, "admin")
    resp = _put(client, token, target_id, {
        "overrides": [
            {"permission_code": "totally.fake_perm", "effect": "grant"},
        ],
    })
    assert resp.status_code == 404
    msg = resp.get_json().get("message", "")
    assert "totally.fake_perm" in msg


def test_put_revoke_of_perm_role_does_not_have_returns_422(app, client):
    """No se permite revoke sobre un perm que el rol del target no concede."""
    _seed(app)
    # editor NO tiene audit.read; revoke huérfano debe fallar.
    target_id = _make_user(app, "editor", "d3-val-orph@x.co")
    _clear_overrides(app, target_id)
    token = _token_for(client, app, "admin")
    resp = _put(client, token, target_id, {
        "overrides": [
            {"permission_code": "audit.read", "effect": "revoke"},
        ],
    })
    assert resp.status_code == 422
    msg = resp.get_json().get("message", "")
    assert "audit.read" in msg
    assert "editor" in msg


def test_put_validation_failure_does_not_persist(app, client):
    """Si un override del body falla validación, NADA se persiste."""
    _seed(app)
    target_id = _make_user(app, "editor", "d3-val-atomic@x.co")
    _clear_overrides(app, target_id)
    # Sembramos un override pre-existente que NO debería tocarse.
    from app.shared.models.user_permission import UserPermission
    from app.shared.models.permission import Permission
    with app.app_context():
        p = Permission.query.filter_by(code="audit.read").first()
        db.session.add(UserPermission(
            user_id=target_id, permission_id=p.id, effect="grant",
        ))
        db.session.commit()
    before = _overrides_of(app, target_id)

    token = _token_for(client, app, "admin")
    resp = _put(client, token, target_id, {
        "overrides": [
            {"permission_code": "users.read_basic", "effect": "grant"},
            {"permission_code": "no.existe", "effect": "grant"},
        ],
    })
    assert resp.status_code == 404
    after = _overrides_of(app, target_id)
    assert before == after, "No debió persistirse nada cuando hay error"


# ═════════════════════════════════════════════════════════════════════════
# Bulk replace semantics
# ═════════════════════════════════════════════════════════════════════════


def test_put_empty_list_removes_all_existing_overrides(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d3-sem-empty@x.co")
    _clear_overrides(app, target_id)

    # Setup: sembramos 2 overrides.
    token = _token_for(client, app, "admin")
    setup = _put(client, token, target_id, {
        "overrides": [
            {"permission_code": "audit.read", "effect": "grant"},
            {"permission_code": "users.read_basic", "effect": "grant"},
        ],
    })
    assert setup.status_code == 200, setup.get_data(as_text=True)
    assert len(_overrides_of(app, target_id)) == 2

    resp = _put(client, token, target_id, {"overrides": []})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _overrides_of(app, target_id) == set()

    payload = resp.get_json()
    assert payload["overrides"] == []


def test_put_change_grant_to_revoke_audits_changed(app, client):
    _seed(app)
    from app.shared.models.audit_log import AuditLog
    # editor tiene reports.read en su bundle → revoke es válido.
    target_id = _make_user(app, "editor", "d3-sem-change@x.co")
    _clear_overrides(app, target_id)

    token = _token_for(client, app, "admin")
    # Setup: grant de users.read_basic.
    setup = _put(client, token, target_id, {
        "overrides": [{"permission_code": "users.read_basic", "effect": "grant"}],
    })
    assert setup.status_code == 200

    # Acto: cambiamos grant → revoke. users.read_basic ES parte del bundle
    # editor (sí lo tiene), entonces revoke es válido semánticamente.
    resp = _put(client, token, target_id, {
        "overrides": [{"permission_code": "users.read_basic", "effect": "revoke"}],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)

    with app.app_context():
        log = (
            AuditLog.query
            .filter_by(entity="user_permission_overrides", entity_id=target_id)
            .order_by(AuditLog.id.desc())
            .first()
        )
        detail = json.loads(log.detail)
    assert detail["added"] == []
    assert detail["removed"] == []
    assert detail["changed"] == [{
        "permission_code": "users.read_basic",
        "from": "grant",
        "to": "revoke",
    }]


def test_put_noop_does_not_emit_audit_log(app, client):
    """Mismo set → no debe haber AuditLog nuevo."""
    _seed(app)
    from app.shared.models.audit_log import AuditLog

    target_id = _make_user(app, "editor", "d3-sem-noop@x.co")
    _clear_overrides(app, target_id)
    token = _token_for(client, app, "admin")

    # Setup: grant de audit.read.
    setup_body = {"overrides": [{"permission_code": "audit.read", "effect": "grant"}]}
    setup = _put(client, token, target_id, setup_body)
    assert setup.status_code == 200

    with app.app_context():
        before = AuditLog.query.filter_by(
            entity="user_permission_overrides", entity_id=target_id,
        ).count()

    # No-op: mismo body.
    resp = _put(client, token, target_id, setup_body)
    assert resp.status_code == 200

    with app.app_context():
        after = AuditLog.query.filter_by(
            entity="user_permission_overrides", entity_id=target_id,
        ).count()
    assert after == before, "No-op no debe emitir AuditLog"


def test_put_idempotent_repeated_same_body(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d3-sem-idem@x.co")
    _clear_overrides(app, target_id)
    token = _token_for(client, app, "admin")
    body = {"overrides": [{"permission_code": "audit.read", "effect": "grant"}]}

    r1 = _put(client, token, target_id, body)
    r2 = _put(client, token, target_id, body)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert _overrides_of(app, target_id) == {("audit.read", "grant")}


# ═════════════════════════════════════════════════════════════════════════
# Lockouts — self
# ═════════════════════════════════════════════════════════════════════════


CRITICAL_LIST = sorted([
    "roles.read", "roles.manage", "users.manage",
    "users.manage_permissions", "users.read_permissions",
])


@pytest.mark.parametrize("critical_code", CRITICAL_LIST)
def test_put_self_lockout_revoke_critical(app, client, critical_code):
    """admin no puede revocarse a sí mismo un permiso crítico."""
    _seed(app)
    # Login como admin nuevo dedicado al test, descubrimos su ID.
    from app.shared.models.user import User
    email = f"d3-self-{critical_code.replace('.', '_')}@x.co"
    admin_id = _make_user(app, "admin", email)
    token = _login(client, email, "pw")

    resp = _put(client, token, admin_id, {
        "overrides": [{"permission_code": critical_code, "effect": "revoke"}],
    })
    assert resp.status_code == 403, resp.get_data(as_text=True)
    msg = resp.get_json().get("message", "")
    assert critical_code in msg


# ═════════════════════════════════════════════════════════════════════════
# Lockouts — main admin
# ═════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("critical_code", CRITICAL_LIST)
def test_put_main_admin_lockout_revoke_critical(app, client, critical_code):
    """Otro admin (no-main) intenta revocar crítico al main_admin → 403."""
    _seed(app)
    main_id = _make_user(
        app, "admin",
        f"d3-main-tgt-{critical_code.replace('.', '_')}@x.co",
        is_main_admin=True,
    )
    actor_email = f"d3-main-actor-{critical_code.replace('.', '_')}@x.co"
    _make_user(app, "admin", actor_email, is_main_admin=False)
    token = _login(client, actor_email, "pw")

    resp = _put(client, token, main_id, {
        "overrides": [{"permission_code": critical_code, "effect": "revoke"}],
    })
    assert resp.status_code == 403, resp.get_data(as_text=True)
    msg = resp.get_json().get("message", "")
    assert critical_code in msg


# ═════════════════════════════════════════════════════════════════════════
# Lockouts — admin colectivo
# ═════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("critical_code", CRITICAL_LIST)
def test_put_admin_collective_lockout_revoke_critical(app, client, critical_code):
    """Admin intenta revocar crítico a OTRO usuario con rol admin (no main,
    no self) → 403."""
    _seed(app)
    # Crear target admin (no-main).
    target_email = f"d3-adm-tgt-{critical_code.replace('.', '_')}@x.co"
    target_id = _make_user(app, "admin", target_email, is_main_admin=False)
    # Actor admin distinto al target.
    actor_email = f"d3-adm-actor-{critical_code.replace('.', '_')}@x.co"
    _make_user(app, "admin", actor_email, is_main_admin=False)
    assert _make_user(app, "admin", actor_email) != target_id

    token = _login(client, actor_email, "pw")
    resp = _put(client, token, target_id, {
        "overrides": [{"permission_code": critical_code, "effect": "revoke"}],
    })
    assert resp.status_code == 403, resp.get_data(as_text=True)
    msg = resp.get_json().get("message", "")
    assert critical_code in msg


# ═════════════════════════════════════════════════════════════════════════
# Lockouts — escenarios positivos
# ═════════════════════════════════════════════════════════════════════════


def test_put_grant_critical_to_editor_ok(app, client):
    """Grant de un crítico a un editor es escalación intencional → permitido."""
    _seed(app)
    editor_id = _make_user(app, "editor", "d3-pos-grant-crit@x.co")
    _clear_overrides(app, editor_id)
    token = _token_for(client, app, "admin")
    resp = _put(client, token, editor_id, {
        "overrides": [{"permission_code": "users.manage", "effect": "grant"}],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert ("users.manage", "grant") in _overrides_of(app, editor_id)


def test_put_revoke_non_critical_to_main_admin_ok(app, client):
    """Revocar un perm NO crítico al main_admin sí está permitido."""
    _seed(app)
    main_id = _make_user(app, "admin", "d3-pos-revoke-nc@x.co", is_main_admin=True)
    _clear_overrides(app, main_id)
    actor_email = "d3-pos-rnc-actor@x.co"
    _make_user(app, "admin", actor_email, is_main_admin=False)
    token = _login(client, actor_email, "pw")

    # admin tiene reports.read en su bundle → revoke es válido.
    resp = _put(client, token, main_id, {
        "overrides": [{"permission_code": "reports.read", "effect": "revoke"}],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert ("reports.read", "revoke") in _overrides_of(app, main_id)


# ═════════════════════════════════════════════════════════════════════════
# AuditLog
# ═════════════════════════════════════════════════════════════════════════


def test_put_emits_exactly_one_audit_log_on_change(app, client):
    _seed(app)
    from app.shared.models.audit_log import AuditLog

    target_id = _make_user(app, "editor", "d3-aud-one@x.co")
    _clear_overrides(app, target_id)
    token = _token_for(client, app, "admin")

    with app.app_context():
        before = AuditLog.query.filter_by(
            entity="user_permission_overrides", entity_id=target_id,
        ).count()

    resp = _put(client, token, target_id, {
        "overrides": [{"permission_code": "audit.read", "effect": "grant"}],
    })
    assert resp.status_code == 200

    with app.app_context():
        after = AuditLog.query.filter_by(
            entity="user_permission_overrides", entity_id=target_id,
        ).count()
    assert after - before == 1


def test_put_audit_log_fields_are_correct(app, client):
    _seed(app)
    from app.shared.models.audit_log import AuditLog
    from app.shared.models.user import User

    target_id = _make_user(app, "editor", "d3-aud-fields@x.co")
    _clear_overrides(app, target_id)
    actor_email = "d3-aud-fields-actor@x.co"
    actor_id = _make_user(app, "admin", actor_email)
    token = _login(client, actor_email, "pw")

    resp = _put(client, token, target_id, {
        "overrides": [{"permission_code": "audit.read", "effect": "grant"}],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)

    with app.app_context():
        log = (
            AuditLog.query
            .filter_by(entity="user_permission_overrides", entity_id=target_id)
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert log is not None
        assert log.entity == "user_permission_overrides"
        assert log.entity_id == target_id
        assert log.action == "updated"
        assert log.user_id == actor_id


def test_put_audit_log_detail_shape(app, client):
    _seed(app)
    from app.shared.models.audit_log import AuditLog

    target_id = _make_user(app, "editor", "d3-aud-shape@x.co")
    _clear_overrides(app, target_id)
    token = _token_for(client, app, "admin")

    # 1ra llamada: añade audit.read (grant).
    resp1 = _put(client, token, target_id, {
        "overrides": [{"permission_code": "audit.read", "effect": "grant"}],
    })
    assert resp1.status_code == 200

    # 2da llamada: cambia audit.read grant→revoke (audit.read está fuera del
    # bundle editor → revoke huérfano). Para evitar 422, mejor:
    # añade users.read_basic (grant) y quita audit.read (vuelve a default).
    resp2 = _put(client, token, target_id, {
        "overrides": [
            {"permission_code": "users.read_basic", "effect": "grant"},
        ],
    })
    assert resp2.status_code == 200, resp2.get_data(as_text=True)

    with app.app_context():
        log = (
            AuditLog.query
            .filter_by(entity="user_permission_overrides", entity_id=target_id)
            .order_by(AuditLog.id.desc())
            .first()
        )
        detail = json.loads(log.detail)

    assert set(detail.keys()) == {
        "target_user", "added", "removed", "changed", "shadow_mode_active",
    }
    assert detail["target_user"]["id"] == target_id
    assert detail["target_user"]["email"] == "d3-aud-shape@x.co"
    # added: users.read_basic (grant).
    assert detail["added"] == [
        {"permission_code": "users.read_basic", "effect": "grant"}
    ]
    # removed: audit.read (grant) (volvió a no estar).
    assert detail["removed"] == [
        {"permission_code": "audit.read", "effect": "grant"}
    ]
    assert detail["changed"] == []
    assert isinstance(detail["shadow_mode_active"], bool)


def test_put_audit_detail_is_deterministic_json(app, client):
    """sort_keys=True → diffs estables en CI."""
    _seed(app)
    from app.shared.models.audit_log import AuditLog

    target_id = _make_user(app, "editor", "d3-aud-det@x.co")
    _clear_overrides(app, target_id)
    token = _token_for(client, app, "admin")

    resp = _put(client, token, target_id, {
        "overrides": [{"permission_code": "audit.read", "effect": "grant"}],
    })
    assert resp.status_code == 200

    with app.app_context():
        log = (
            AuditLog.query
            .filter_by(entity="user_permission_overrides", entity_id=target_id)
            .order_by(AuditLog.id.desc())
            .first()
        )
        raw = log.detail
    parsed = json.loads(raw)
    re_serialized = json.dumps(parsed, sort_keys=True)
    assert raw == re_serialized


def test_put_audit_log_reflects_shadow_mode(app, client):
    _seed(app)
    from app.shared.models.audit_log import AuditLog

    target_id = _make_user(app, "editor", "d3-aud-shadow@x.co")
    _clear_overrides(app, target_id)
    token = _token_for(client, app, "admin")

    app.config["PERM_SHADOW_MODE"] = True
    try:
        resp = _put(client, token, target_id, {
            "overrides": [{"permission_code": "audit.read", "effect": "grant"}],
        })
        assert resp.status_code == 200
        with app.app_context():
            log = (
                AuditLog.query
                .filter_by(
                    entity="user_permission_overrides", entity_id=target_id,
                )
                .order_by(AuditLog.id.desc())
                .first()
            )
            detail = json.loads(log.detail)
        assert detail["shadow_mode_active"] is True
    finally:
        app.config["PERM_SHADOW_MODE"] = False

    # Ahora con shadow_mode=False (verificamos que el flag baja).
    resp2 = _put(client, token, target_id, {
        "overrides": [
            {"permission_code": "audit.read", "effect": "grant"},
            {"permission_code": "users.read_basic", "effect": "grant"},
        ],
    })
    assert resp2.status_code == 200
    with app.app_context():
        log = (
            AuditLog.query
            .filter_by(entity="user_permission_overrides", entity_id=target_id)
            .order_by(AuditLog.id.desc())
            .first()
        )
        detail = json.loads(log.detail)
    assert detail["shadow_mode_active"] is False


# ═════════════════════════════════════════════════════════════════════════
# Cache invalidation
# ═════════════════════════════════════════════════════════════════════════


def test_put_invalidates_effective_permissions_cache(app, client):
    """Tras PUT, el set efectivo del target refleja el cambio.

    Asume que `get_effective_permissions(target)` debería devolver el set
    actualizado tras el commit, no un valor cacheado. Verificamos via el
    endpoint /users/:id/permissions (D1) que sí refleje el override.
    """
    _seed(app)
    target_id = _make_user(app, "viewer", "d3-cache@x.co")
    _clear_overrides(app, target_id)
    token = _token_for(client, app, "admin")

    # State inicial: viewer sólo tiene reports.read.
    before_resp = client.get(
        f"/users/{target_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert before_resp.status_code == 200
    before_eff = set(before_resp.get_json()["effective"])
    assert "users.read_basic" not in before_eff

    # PUT: grant de users.read_basic.
    put_resp = _put(client, token, target_id, {
        "overrides": [{"permission_code": "users.read_basic", "effect": "grant"}],
    })
    assert put_resp.status_code == 200, put_resp.get_data(as_text=True)

    # GET nuevamente: debe incluir el grant.
    after_resp = client.get(
        f"/users/{target_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    after_eff = set(after_resp.get_json()["effective"])
    assert "users.read_basic" in after_eff


def test_put_response_effective_reflects_change(app, client):
    """El campo `permissions.effective` del response post-PUT debe ser
    el resultado de aplicar el override (no el set pre-cambio)."""
    _seed(app)
    target_id = _make_user(app, "viewer", "d3-cache-resp@x.co")
    _clear_overrides(app, target_id)
    token = _token_for(client, app, "admin")
    resp = _put(client, token, target_id, {
        "overrides": [
            {"permission_code": "users.read_basic", "effect": "grant"},
            {"permission_code": "reports.read", "effect": "revoke"},
        ],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    permissions = resp.get_json()["permissions"]
    effective = set(permissions["effective"])
    # users.read_basic se otorgó vía grant → en effective.
    assert "users.read_basic" in effective
    # reports.read del rol viewer fue revocado → NO en effective.
    assert "reports.read" not in effective


# ═════════════════════════════════════════════════════════════════════════
# Response shape
# ═════════════════════════════════════════════════════════════════════════


def test_put_response_shape(app, client):
    _seed(app)
    target_id = _make_user(app, "editor", "d3-resp-shape@x.co")
    _clear_overrides(app, target_id)
    token = _token_for(client, app, "admin")
    resp = _put(client, token, target_id, {
        "overrides": [{"permission_code": "audit.read", "effect": "grant"}],
    })
    assert resp.status_code == 200
    payload = resp.get_json()
    assert {"overrides", "permissions"}.issubset(payload.keys())

    # overrides: lista de UserPermissionOverrideSchema.
    assert isinstance(payload["overrides"], list)
    assert len(payload["overrides"]) == 1
    o = payload["overrides"][0]
    assert {"permission", "effect", "granted_by", "granted_at"}.issubset(o.keys())
    assert o["permission"]["code"] == "audit.read"
    assert o["effect"] == "grant"

    # permissions: UserPermissionsViewSchema (from_role/grants/revokes/effective).
    perms = payload["permissions"]
    assert {"user", "from_role", "grants", "revokes", "effective"}.issubset(
        perms.keys(),
    )
    for k in ("from_role", "grants", "revokes", "effective"):
        assert isinstance(perms[k], list)
    assert "audit.read" in perms["grants"]
    assert "audit.read" in perms["effective"]


def test_put_response_effective_matches_formula(app, client):
    """`permissions.effective` debe ser exactamente
    `(from_role ∪ grants) − revokes`."""
    _seed(app)
    target_id = _make_user(app, "viewer", "d3-resp-formula@x.co")
    _clear_overrides(app, target_id)
    token = _token_for(client, app, "admin")
    resp = _put(client, token, target_id, {
        "overrides": [
            {"permission_code": "users.read_basic", "effect": "grant"},
            {"permission_code": "reports.read", "effect": "revoke"},
        ],
    })
    assert resp.status_code == 200
    perms = resp.get_json()["permissions"]
    from_role = set(perms["from_role"])
    grants = set(perms["grants"])
    revokes = set(perms["revokes"])
    effective = set(perms["effective"])
    assert effective == (from_role | grants) - revokes


def test_put_granted_by_is_recorded_in_overrides(app, client):
    """granted_by debe apuntar al actor en cada override creado."""
    _seed(app)
    target_id = _make_user(app, "editor", "d3-grant-by@x.co")
    _clear_overrides(app, target_id)
    actor_email = "d3-gby-actor@x.co"
    actor_id = _make_user(app, "admin", actor_email)
    token = _login(client, actor_email, "pw")

    resp = _put(client, token, target_id, {
        "overrides": [{"permission_code": "audit.read", "effect": "grant"}],
    })
    assert resp.status_code == 200
    payload = resp.get_json()
    o = payload["overrides"][0]
    assert o["granted_by"] is not None
    assert o["granted_by"]["id"] == actor_id
    assert o["granted_by"]["email"] == actor_email
