"""Tests del comando `flask seed_permissions` (Bloque 4).

Verifican:
- Idempotencia: correr 2 veces no duplica nada.
- Crea el rol `monitor` aunque no exista.
- No sobrescribe bundles ya modificados (preserva ediciones admin).
- Huérfanos en BD se reportan pero NO se borran.
- Todo se resuelve por `role.name` y `permission.code`, no por IDs fijos.
"""
import pytest
from click.testing import CliRunner

from app.core.extensions import db


@pytest.fixture
def runner(app):
    """CLI runner que ejecuta dentro del contexto de la app de tests."""
    return app.test_cli_runner()


def _invoke_seed(runner):
    """Invoca el comando y devuelve el `Result`. Falla el test si exit != 0."""
    from app.modules.indicators.commands.seed_permissions import seed_permissions
    result = runner.invoke(seed_permissions)
    assert result.exit_code == 0, f"seed_permissions falló:\n{result.output}\n{result.exception}"
    return result


def _clean_rbac(app):
    """Limpia tablas RBAC entre tests (BD en memoria; no afecta prod)."""
    from app.shared.models.permission import Permission
    from app.shared.models.role import Role
    from app.shared.models.role_permission import RolePermission
    with app.app_context():
        RolePermission.query.delete()
        Permission.query.delete()
        # Roles los conservamos: pueden existir desde otros tests; el
        # seeder los respeta y deja sus permisos como estén.
        Role.query.delete()
        db.session.commit()


def test_seed_creates_all_perms_and_roles(app, runner):
    _clean_rbac(app)
    _invoke_seed(runner)

    with app.app_context():
        from app.shared.models.permission import Permission
        from app.shared.models.role import Role
        from app.shared.permissions.catalog import ALL_PERMISSIONS

        # 30 permisos en BD.
        codes_db = {p.code for p in Permission.query.all()}
        codes_cat = {p.code for p in ALL_PERMISSIONS}
        assert codes_db == codes_cat

        # 4 roles canónicos con is_system=True.
        roles = {r.name: r for r in Role.query.all()}
        for canonical in ("admin", "monitor", "editor", "viewer"):
            assert canonical in roles, f"Falta rol {canonical}"
            assert roles[canonical].is_system is True
            assert roles[canonical].description


def test_seed_is_idempotent(app, runner):
    _clean_rbac(app)
    _invoke_seed(runner)
    _invoke_seed(runner)
    _invoke_seed(runner)

    with app.app_context():
        from app.shared.models.permission import Permission
        from app.shared.models.role import Role
        from app.shared.models.role_permission import RolePermission
        from app.shared.permissions.catalog import ALL_PERMISSIONS

        # No duplica permissions.
        assert Permission.query.count() == len(ALL_PERMISSIONS)
        # No duplica role_permissions (PK compuesta los protege en BD,
        # pero el seeder no debe siquiera intentarlo).
        # Verificamos que los conteos por rol coincidan con los bundles.
        from app.modules.indicators.commands.seed_permissions import BUNDLES
        for name, codes in BUNDLES.items():
            role = Role.query.filter_by(name=name).first()
            assert role is not None
            assert len(role.role_permissions) == len(codes), (
                f"rol {name} tiene {len(role.role_permissions)} perms, "
                f"esperados {len(codes)}"
            )


def test_seed_auto_creates_monitor_when_missing(app, runner):
    _clean_rbac(app)
    # Pre-condición: monitor NO existe.
    with app.app_context():
        from app.shared.models.role import Role
        assert Role.query.filter_by(name="monitor").first() is None

    _invoke_seed(runner)

    with app.app_context():
        from app.shared.models.role import Role
        monitor = Role.query.filter_by(name="monitor").first()
        assert monitor is not None
        assert monitor.is_system is True
        # Y tiene su bundle aplicado.
        assert len(monitor.role_permissions) > 0


def test_seed_does_not_overwrite_existing_bundle(app, runner):
    """Si un rol ya tiene permisos (edición admin), el seeder NO los toca."""
    _clean_rbac(app)
    _invoke_seed(runner)

    with app.app_context():
        from app.shared.models.role import Role
        from app.shared.models.permission import Permission
        from app.shared.models.role_permission import RolePermission

        # Simulamos que el admin operativo limpió todos los permisos del rol
        # viewer y le dejó UNO específico distinto al bundle inicial.
        viewer = Role.query.filter_by(name="viewer").first()
        RolePermission.query.filter_by(role_id=viewer.id).delete()
        custom_perm = Permission.query.filter_by(code="reports.create").first()
        db.session.add(RolePermission(
            role_id=viewer.id, permission_id=custom_perm.id
        ))
        db.session.commit()

    # Re-seedea
    _invoke_seed(runner)

    with app.app_context():
        from app.shared.models.role import Role
        from app.shared.models.role_permission import RolePermission
        from app.shared.models.permission import Permission

        viewer = Role.query.filter_by(name="viewer").first()
        # Conservó la configuración custom (1 permiso: reports.create) — el
        # bundle inicial (reports.read) NO se aplicó porque ya había algo.
        assert len(viewer.role_permissions) == 1
        custom_perm = Permission.query.filter_by(code="reports.create").first()
        assert viewer.role_permissions[0].permission_id == custom_perm.id


def test_seed_reports_orphans_without_deleting(app, runner):
    """Permisos en BD que ya no están en catálogo se reportan pero quedan."""
    _clean_rbac(app)
    _invoke_seed(runner)

    with app.app_context():
        from app.shared.models.permission import Permission
        # Inyectamos un permiso huérfano (no está en catalog.py).
        orphan = Permission(
            code="legacy.deprecated_action",
            description="Permiso viejo de prueba",
            module="legacy",
            is_system=False,
        )
        db.session.add(orphan)
        db.session.commit()
        orphan_id = orphan.id

    result = _invoke_seed(runner)
    assert "huérfanos" in result.output.lower() or "huerfanos" in result.output.lower()

    with app.app_context():
        from app.shared.models.permission import Permission
        # NO se borró.
        survived = Permission.query.get(orphan_id)
        assert survived is not None
        assert survived.code == "legacy.deprecated_action"


def test_seed_bundles_resolve_by_code_not_id(app, runner):
    """Los bundles siempre se resuelven por code, no por id.

    Se simula reordenando los IDs (creando un Permission con id alto antes
    del seeder) para asegurar que el seeder no asume IDs contiguos.
    """
    _clean_rbac(app)
    with app.app_context():
        from app.shared.models.permission import Permission
        # Permiso "decoy" con id alto y código que NO existe en catálogo.
        # El seeder debe seguir resolviendo todo correctamente por code.
        decoy = Permission(
            code="zzz.decoy_high_id",
            description="decoy",
            module="legacy",
            is_system=False,
        )
        db.session.add(decoy)
        db.session.commit()

    _invoke_seed(runner)

    with app.app_context():
        from app.shared.models.role import Role
        from app.modules.indicators.commands.seed_permissions import BUNDLE_ADMIN

        admin = Role.query.filter_by(name="admin").first()
        admin_codes = {assoc.permission.code for assoc in admin.role_permissions}
        # admin tiene exactamente los codes del bundle (decoy NO está).
        assert admin_codes == set(BUNDLE_ADMIN)
        assert "zzz.decoy_high_id" not in admin_codes
