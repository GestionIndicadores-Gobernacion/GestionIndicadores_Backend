"""Tests de invariantes RBAC (Bloque 11):
- is_main_admin se backfilea por email seedeado.
- assert_can_delete_role bloquea roles del sistema y roles con usuarios.
- assert_can_modify_user_permissions protege al main admin y al actor.
- assert_can_change_user_role protege main admin y auto-degradación.
- UserSchema expone is_main_admin.
"""
import pytest

from app.core.extensions import db


def _seed(app):
    from app.modules.indicators.commands.seed_permissions import seed_permissions
    result = app.test_cli_runner().invoke(seed_permissions)
    assert result.exit_code == 0, result.output


def _make_user(app, role_name, email, is_main_admin=False):
    from app.shared.models.user import User
    from app.shared.models.role import Role
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        u = User.query.filter_by(email=email).first()
        if u is None:
            u = User(
                first_name="T", last_name="T", email=email, role_id=role.id,
                is_main_admin=is_main_admin,
            )
            u.set_password("pw")
            db.session.add(u)
            db.session.commit()
        return u.id


# ─── User model + Schema ──────────────────────────────────────────────────

def test_user_schema_exposes_is_main_admin(app):
    _seed(app)
    uid = _make_user(app, "admin", "main-admin-test@x.co", is_main_admin=True)
    with app.app_context():
        from app.shared.models.user import User
        from app.shared.schemas.user_schema import UserSchema
        u = User.query.get(uid)
        dump = UserSchema().dump(u)
        assert dump.get("is_main_admin") is True


# ─── assert_can_delete_role ───────────────────────────────────────────────

def test_cannot_delete_system_role(app):
    _seed(app)
    with app.app_context():
        from app.shared.models.role import Role
        from app.utils.rbac_invariants import (
            assert_can_delete_role, RBACInvariantError,
        )
        admin_role = Role.query.filter_by(name="admin").first()
        with pytest.raises(RBACInvariantError):
            assert_can_delete_role(admin_role)


def test_cannot_delete_role_with_users(app):
    _seed(app)
    _make_user(app, "editor", "to-protect-editor-role@x.co")
    with app.app_context():
        from app.shared.models.role import Role
        from app.utils.rbac_invariants import (
            assert_can_delete_role, RBACInvariantError,
        )
        # Creamos un rol custom no-system con un usuario asignado.
        custom = Role.query.filter_by(name="contractor").first()
        if not custom:
            custom = Role(name="contractor", description="custom", is_system=False)
            db.session.add(custom)
            db.session.commit()
        # Asignamos un usuario.
        from app.shared.models.user import User
        u = User.query.filter_by(email="to-protect-editor-role@x.co").first()
        u.role_id = custom.id
        db.session.commit()
        db.session.refresh(custom)

        with pytest.raises(RBACInvariantError):
            assert_can_delete_role(custom)


def test_can_delete_empty_custom_role(app):
    _seed(app)
    with app.app_context():
        from app.shared.models.role import Role
        from app.utils.rbac_invariants import assert_can_delete_role
        custom = Role(name="empty_role", description="x", is_system=False)
        db.session.add(custom)
        db.session.commit()
        # No debe lanzar.
        assert_can_delete_role(custom)


# ─── assert_can_modify_user_permissions ───────────────────────────────────

def test_cannot_revoke_critical_perm_to_main_admin(app):
    _seed(app)
    main_id = _make_user(app, "admin", "ma-revoke@x.co", is_main_admin=True)
    actor_id = _make_user(app, "admin", "actor-1@x.co", is_main_admin=False)
    with app.app_context():
        from app.shared.models.user import User
        from app.utils.rbac_invariants import (
            assert_can_modify_user_permissions, RBACInvariantError,
        )
        actor = User.query.get(actor_id)
        target = User.query.get(main_id)
        with pytest.raises(RBACInvariantError):
            assert_can_modify_user_permissions(
                actor, target, "users.manage", "revoke",
            )


def test_actor_cannot_self_degrade_critical_perm(app):
    _seed(app)
    aid = _make_user(app, "admin", "self-degrade@x.co")
    with app.app_context():
        from app.shared.models.user import User
        from app.utils.rbac_invariants import (
            assert_can_modify_user_permissions, RBACInvariantError,
        )
        u = User.query.get(aid)
        with pytest.raises(RBACInvariantError):
            assert_can_modify_user_permissions(u, u, "users.manage_permissions", "revoke")


def test_can_grant_perms_to_main_admin(app):
    _seed(app)
    main_id = _make_user(app, "admin", "ma-grant@x.co", is_main_admin=True)
    actor_id = _make_user(app, "admin", "actor-2@x.co")
    with app.app_context():
        from app.shared.models.user import User
        from app.utils.rbac_invariants import assert_can_modify_user_permissions
        actor = User.query.get(actor_id)
        target = User.query.get(main_id)
        # Otorgar (no revoke) está permitido.
        assert_can_modify_user_permissions(actor, target, "users.manage", "grant")


def test_can_revoke_non_critical_perm_to_main_admin(app):
    _seed(app)
    main_id = _make_user(app, "admin", "ma-noncrit@x.co", is_main_admin=True)
    actor_id = _make_user(app, "admin", "actor-3@x.co")
    with app.app_context():
        from app.shared.models.user import User
        from app.utils.rbac_invariants import assert_can_modify_user_permissions
        actor = User.query.get(actor_id)
        target = User.query.get(main_id)
        # Revocar permiso no-crítico: permitido.
        assert_can_modify_user_permissions(actor, target, "reports.read", "revoke")


# ─── assert_can_change_user_role ──────────────────────────────────────────

def test_cannot_change_main_admin_role(app):
    _seed(app)
    main_id = _make_user(app, "admin", "ma-role@x.co", is_main_admin=True)
    actor_id = _make_user(app, "admin", "actor-4@x.co")
    with app.app_context():
        from app.shared.models.user import User
        from app.shared.models.role import Role
        from app.utils.rbac_invariants import (
            assert_can_change_user_role, RBACInvariantError,
        )
        actor = User.query.get(actor_id)
        target = User.query.get(main_id)
        editor_role = Role.query.filter_by(name="editor").first()
        with pytest.raises(RBACInvariantError):
            assert_can_change_user_role(actor, target, editor_role)


def test_actor_cannot_self_change_to_non_admin(app):
    _seed(app)
    aid = _make_user(app, "admin", "self-role@x.co")
    with app.app_context():
        from app.shared.models.user import User
        from app.shared.models.role import Role
        from app.utils.rbac_invariants import (
            assert_can_change_user_role, RBACInvariantError,
        )
        u = User.query.get(aid)
        viewer_role = Role.query.filter_by(name="viewer").first()
        with pytest.raises(RBACInvariantError):
            assert_can_change_user_role(u, u, viewer_role)
