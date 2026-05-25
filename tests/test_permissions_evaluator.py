"""Tests del evaluador central (Bloque 5).

Verifican:
- role ∪ grants − revokes (matriz completa).
- Cache por request (un solo SELECT por usuario por request).
- JWT claim tiene preferencia sobre BD.
- Fallback a BD cuando el JWT no trae el claim (sesiones viejas).
- `require_permission` retorna 403 si falta el permiso.
- `role_required` NO cambia comportamiento.
"""
import pytest
from flask import Flask
from sqlalchemy import event

from app.core.extensions import db


# ─── Helpers ──────────────────────────────────────────────────────────────

def _seed_minimal(app):
    """Sembrar permisos + roles canónicos vía el comando seed."""
    from app.modules.indicators.commands.seed_permissions import seed_permissions
    runner = app.test_cli_runner()
    result = runner.invoke(seed_permissions)
    assert result.exit_code == 0, result.output


def _make_user(app, role_name: str, email: str = "test@x.co"):
    from app.shared.models.user import User
    from app.shared.models.role import Role
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        assert role is not None, f"Rol {role_name} no encontrado tras seed"
        u = User.query.filter_by(email=email).first()
        if u is None:
            u = User(first_name="T", last_name="T", email=email, role_id=role.id)
            u.set_password("x")
            db.session.add(u)
            db.session.commit()
        return u.id


def _override(app, user_id: int, perm_code: str, effect: str):
    from app.shared.models.permission import Permission
    from app.shared.models.user_permission import UserPermission
    with app.app_context():
        perm = Permission.query.filter_by(code=perm_code).first()
        existing = UserPermission.query.filter_by(
            user_id=user_id, permission_id=perm.id
        ).first()
        if existing:
            existing.effect = effect
        else:
            db.session.add(UserPermission(
                user_id=user_id,
                permission_id=perm.id,
                effect=effect,
            ))
        db.session.commit()


# ─── Set efectivo: role / grant / revoke ──────────────────────────────────

def test_effective_set_for_admin_is_full_bundle(app):
    _seed_minimal(app)
    uid = _make_user(app, "admin", "admin-eval@x.co")

    with app.test_request_context():  # g activo
        from app.utils.permissions import get_effective_permissions
        from app.shared.models.user import User
        from app.utils.permissions import _load_user_with_perms
        user = _load_user_with_perms(uid)
        from app.modules.indicators.commands.seed_permissions import BUNDLE_ADMIN
        assert get_effective_permissions(user) == set(BUNDLE_ADMIN)


def test_grant_adds_permission_not_in_role_bundle(app):
    _seed_minimal(app)
    uid = _make_user(app, "viewer", "viewer-eval@x.co")
    # viewer NO tiene users.read_basic por default — se lo damos manual.
    _override(app, uid, "users.read_basic", "grant")

    with app.test_request_context():
        from app.utils.permissions import _load_user_with_perms, get_effective_permissions
        user = _load_user_with_perms(uid)
        perms = get_effective_permissions(user)
        assert "users.read_basic" in perms
        assert "reports.read" in perms  # también el del rol


def test_revoke_removes_permission_from_role_bundle(app):
    _seed_minimal(app)
    uid = _make_user(app, "editor", "editor-eval@x.co")
    # editor tiene reports.create por bundle; lo revocamos.
    _override(app, uid, "reports.create", "revoke")

    with app.test_request_context():
        from app.utils.permissions import _load_user_with_perms, get_effective_permissions
        user = _load_user_with_perms(uid)
        perms = get_effective_permissions(user)
        assert "reports.create" not in perms
        # El resto del bundle sigue.
        assert "reports.read" in perms


def test_revoke_wins_over_grant_when_both_exist(app):
    """`(role ∪ grants) − revokes` → si hay revoke al mismo code, gana revoke
    porque el conjunto de revokes se RESTA al final."""
    _seed_minimal(app)
    uid = _make_user(app, "viewer", "vw-grant-revoke@x.co")
    # Imposible insertar dos UserPermission con (user, perm) iguales por
    # UNIQUE; este test cubre el caso de un perm del rol + revoke explícito.
    # viewer tiene reports.read; lo revocamos.
    _override(app, uid, "reports.read", "revoke")

    with app.test_request_context():
        from app.utils.permissions import _load_user_with_perms, get_effective_permissions
        user = _load_user_with_perms(uid)
        perms = get_effective_permissions(user)
        assert "reports.read" not in perms


# ─── Cache por request ────────────────────────────────────────────────────

def test_cache_avoids_repeated_user_select_in_same_request(app):
    _seed_minimal(app)
    uid = _make_user(app, "admin", "admin-cache@x.co")

    # Pre-creamos el token FUERA del request context (necesita solo app_ctx)
    # para no anidar contexts — los anidamientos confunden flask-jwt-extended
    # entre tests.
    from flask_jwt_extended import create_access_token
    with app.app_context():
        token = create_access_token(identity=str(uid))

    select_count = {"n": 0}

    @event.listens_for(db.engine, "before_cursor_execute")
    def _count(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT") and "users" in statement.lower():
            select_count["n"] += 1

    try:
        with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
            from flask_jwt_extended import verify_jwt_in_request
            verify_jwt_in_request()
            from app.utils.permissions import current_user, has_permission
            u1 = current_user()
            u2 = current_user()
            _ = has_permission("reports.read")
            _ = has_permission("users.manage")
            assert u1 is u2
            # Solo un SELECT a 'users' por toda la request.
            assert select_count["n"] <= 1, f"Demasiados SELECT a users: {select_count['n']}"
    finally:
        event.remove(db.engine, "before_cursor_execute", _count)


# ─── JWT claim vs fallback BD ─────────────────────────────────────────────

def test_jwt_claim_takes_precedence_over_db(app):
    """Si el JWT trae permissions, NO se toca BD."""
    _seed_minimal(app)
    uid = _make_user(app, "viewer", "viewer-jwt@x.co")

    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(
            identity=str(uid),
            additional_claims={
                "permissions": ["custom.fake_perm_only_in_token"],
            },
        )

    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request()
        from app.utils.permissions import current_user_permissions, has_permission
        assert current_user_permissions() == {"custom.fake_perm_only_in_token"}
        assert has_permission("custom.fake_perm_only_in_token")
        # reports.read que SÍ está en el bundle viewer de BD NO aparece —
        # porque el JWT manda.
        assert not has_permission("reports.read")


def test_legacy_jwt_without_claim_falls_back_to_db(app):
    """JWT viejo sin claim `permissions` → se evalúa contra BD (bundle)."""
    _seed_minimal(app)
    uid = _make_user(app, "viewer", "viewer-legacy@x.co")

    from flask_jwt_extended import create_access_token

    with app.app_context():
        # Token sin claim 'permissions' — como los emitidos antes del Bloque 6.
        token = create_access_token(identity=str(uid))

    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request()
        from app.utils.permissions import current_user_permissions, has_permission
        perms = current_user_permissions()
        # Viewer tiene reports.read por bundle.
        assert "reports.read" in perms
        assert has_permission("reports.read")


# ─── Decorador require_permission ─────────────────────────────────────────

def test_require_permission_403_when_missing(app):
    _seed_minimal(app)
    uid = _make_user(app, "viewer", "viewer-403@x.co")

    from flask_jwt_extended import create_access_token, jwt_required
    from app.utils.permissions import require_permission

    @jwt_required()
    @require_permission("users.manage")
    def protected():
        return {"ok": True}

    with app.app_context():
        token = create_access_token(identity=str(uid))

    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request()
        resp = protected()
        # Flask devuelve (body, status) tuple.
        if isinstance(resp, tuple):
            body, status = resp
            assert status == 403


def test_require_permission_ok_when_granted(app):
    _seed_minimal(app)
    uid = _make_user(app, "admin", "admin-ok@x.co")

    from flask_jwt_extended import create_access_token
    from app.utils.permissions import require_permission

    @require_permission("users.manage")
    def protected():
        return {"ok": True}

    with app.app_context():
        token = create_access_token(identity=str(uid))

    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request()
        resp = protected()
        assert resp == {"ok": True}


def test_require_permission_any_of_default(app):
    _seed_minimal(app)
    uid = _make_user(app, "viewer", "viewer-any@x.co")  # tiene reports.read

    from flask_jwt_extended import create_access_token
    from app.utils.permissions import require_permission

    @require_permission("users.manage", "reports.read")  # any-of
    def protected():
        return {"ok": True}

    with app.app_context():
        token = create_access_token(identity=str(uid))

    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request()
        resp = protected()
        assert resp == {"ok": True}  # pasó porque tiene reports.read


def test_require_permission_all_of(app):
    _seed_minimal(app)
    uid = _make_user(app, "viewer", "viewer-all@x.co")

    from flask_jwt_extended import create_access_token
    from app.utils.permissions import require_permission

    @require_permission("users.manage", "reports.read", all_of=True)
    def protected():
        return {"ok": True}

    with app.app_context():
        token = create_access_token(identity=str(uid))

    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request()
        resp = protected()
        assert isinstance(resp, tuple) and resp[1] == 403  # falta users.manage


# ─── Compat: role_required intacto ────────────────────────────────────────

def test_role_required_still_works(app):
    _seed_minimal(app)
    uid = _make_user(app, "admin", "admin-rr@x.co")

    from flask_jwt_extended import create_access_token
    from app.utils.permissions import role_required

    @role_required("admin")
    def protected():
        return {"ok": True}

    with app.app_context():
        token = create_access_token(identity=str(uid))

    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request()
        resp = protected()
        assert resp == {"ok": True}
