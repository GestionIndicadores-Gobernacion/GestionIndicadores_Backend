"""CLI `flask seed_permissions` — sincroniza catálogo + bundles iniciales.

Idempotente. Diseñado para correrse contra ambientes en cualquier estado:
- BD vacía (post-migración inicial).
- Ambiente parcialmente migrado (roles existentes sin permisos).
- Ambiente ya seedeado (correr de nuevo NO hace daño).
- Ambiente con ediciones manuales en la UI admin (NO las sobrescribe).

Reglas operacionales:
- Todo se resuelve por `role.name` y `permission.code`. NUNCA por IDs.
- Los bundles iniciales se aplican SOLO si el rol no tiene permisos aún;
  esto preserva ediciones admin futuras.
- Permisos huérfanos en BD (codes que ya no están en catálogo) se reportan
  pero NO se borran automáticamente — decisión consciente para evitar
  pérdidas accidentales.
- El rol `monitor` se autogenera si falta (fix histórico).
"""
import click
from flask.cli import with_appcontext

from app.core.extensions import db
from app.shared.models.role import Role
from app.shared.models.permission import Permission
from app.shared.models.role_permission import RolePermission
from app.shared.permissions.catalog import (
    ALL_PERMISSIONS,
    # Constantes para los bundles
    PERM_USERS_READ_BASIC, PERM_USERS_READ,
    PERM_ROLES_READ,
    PERM_DATASETS_READ,
    PERM_REPORTS_CREATE, PERM_REPORTS_READ,
    PERM_REPORTS_UPDATE_OWN, PERM_REPORTS_DELETE_OWN,
    PERM_ACTION_PLANS_CREATE, PERM_ACTION_PLANS_READ,
    PERM_ACTION_PLANS_UPDATE_OWN, PERM_ACTION_PLANS_DELETE_OWN,
    PERM_ACTION_PLANS_REPORT_ACTIVITY, PERM_ACTION_PLANS_ADD_EVIDENCE,
    PERM_ACTION_PLANS_DASHBOARD,
)


# ─── Roles canónicos del sistema ──────────────────────────────────────────
# Descripciones legibles para la UI admin. `is_system=True` se aplica al
# crear o al re-seedear si por alguna razón quedó en false.
SYSTEM_ROLES = {
    "admin":   "Administrador del sistema con todos los permisos.",
    "monitor": "Monitor: lectura amplia, dashboards y capacidad de reportar.",
    "editor":  "Editor: gestiona reportes y planes en sus componentes asignados.",
    "viewer":  "Viewer: lectura básica de reportes.",
}


# ─── Bundles iniciales ────────────────────────────────────────────────────
# Derivados de la matriz histórica de `role_required` + helpers `_is_admin`
# del codebase. Cualquier cambio aquí debe acompañarse de los tests de
# paridad (Bloque 13).
#
# IMPORTANTE: los bundles solo se aplican si el rol está vacío. Esto
# significa que tras la primera corrida del seeder, NO se vuelven a tocar
# — el admin operativo es libre de modificar permisos desde la UI sin
# riesgo de que un re-seed los pise.
BUNDLE_ADMIN = frozenset(p.code for p in ALL_PERMISSIONS)

BUNDLE_MONITOR = frozenset({
    PERM_USERS_READ_BASIC,
    PERM_USERS_READ,
    PERM_ROLES_READ,
    PERM_REPORTS_CREATE,
    PERM_REPORTS_READ,
    PERM_REPORTS_UPDATE_OWN,
    PERM_REPORTS_DELETE_OWN,
    PERM_ACTION_PLANS_CREATE,
    PERM_ACTION_PLANS_READ,
    PERM_ACTION_PLANS_UPDATE_OWN,
    PERM_ACTION_PLANS_DELETE_OWN,
    # PERM_ACTION_PLANS_REPORT_ACTIVITY y PERM_ACTION_PLANS_ADD_EVIDENCE
    # NO se incluyen por default. Son overrides granulares (ver
    # `_can_report_activity` / `_can_add_evidence`): por defecto monitor
    # solo puede reportar/evidenciar planes donde sea responsable. Se
    # asignan desde la UI a usuarios específicos cuando se requiera la
    # excepción.
    PERM_ACTION_PLANS_DASHBOARD,
    PERM_DATASETS_READ,
})

BUNDLE_EDITOR = frozenset({
    PERM_USERS_READ_BASIC,
    PERM_REPORTS_CREATE,
    PERM_REPORTS_READ,
    PERM_REPORTS_UPDATE_OWN,
    PERM_REPORTS_DELETE_OWN,
    PERM_ACTION_PLANS_CREATE,
    PERM_ACTION_PLANS_READ,
    PERM_ACTION_PLANS_UPDATE_OWN,
    PERM_ACTION_PLANS_DELETE_OWN,
    # PERM_ACTION_PLANS_REPORT_ACTIVITY y PERM_ACTION_PLANS_ADD_EVIDENCE
    # idem monitor: overrides granulares, no se dan por default.
    PERM_DATASETS_READ,
})

BUNDLE_VIEWER = frozenset({
    PERM_REPORTS_READ,
})

BUNDLES = {
    "admin":   BUNDLE_ADMIN,
    "monitor": BUNDLE_MONITOR,
    "editor":  BUNDLE_EDITOR,
    "viewer":  BUNDLE_VIEWER,
}


def _upsert_permissions() -> tuple[int, int, list[str]]:
    """Sincroniza la tabla `permissions` con el catálogo.

    Retorna (creados, actualizados, huérfanos_en_BD).
    """
    existing_by_code: dict[str, Permission] = {
        p.code: p for p in Permission.query.all()
    }
    created = 0
    updated = 0

    for entry in ALL_PERMISSIONS:
        existing = existing_by_code.get(entry.code)
        if existing is None:
            db.session.add(Permission(
                code=entry.code,
                description=entry.description,
                module=entry.module,
                is_system=True,
            ))
            created += 1
            continue

        # Mantener metadata sincronizada (description/module pueden cambiar).
        # `is_system` solo se eleva — nunca se baja desde el seeder, para no
        # interferir si el admin marcó algún custom-perm como sistema a mano.
        dirty = False
        if existing.description != entry.description:
            existing.description = entry.description
            dirty = True
        if existing.module != entry.module:
            existing.module = entry.module
            dirty = True
        if not existing.is_system:
            existing.is_system = True
            dirty = True
        if dirty:
            updated += 1

    catalog_codes = {p.code for p in ALL_PERMISSIONS}
    orphans = sorted(set(existing_by_code.keys()) - catalog_codes)
    return created, updated, orphans


def _ensure_role(name: str, description: str) -> Role:
    """Devuelve el rol (por nombre), creándolo si falta. Idempotente."""
    role = Role.query.filter_by(name=name).first()
    if role is None:
        role = Role(name=name, description=description, is_system=True)
        db.session.add(role)
        db.session.flush()  # asegura .id disponible
        click.echo(f"   🧩 rol creado: {name}")
        return role

    # Re-asegurar metadata (idempotente).
    if role.description != description:
        role.description = description
    if not role.is_system:
        role.is_system = True
    return role


def _apply_bundle(role: Role, codes: frozenset[str], code_to_perm: dict[str, Permission]) -> int:
    """Crea RolePermission para `role` con los `codes` dados.

    Solo se ejecuta si el rol no tiene permisos asignados. Retorna cuántos
    permisos quedaron asignados (0 si se preservó configuración existente).
    """
    if role.role_permissions:
        click.echo(
            f"   ⏭️  '{role.name}' ya tiene "
            f"{len(role.role_permissions)} permiso(s) — bundle NO se aplica"
        )
        return 0

    added = 0
    for code in codes:
        perm = code_to_perm.get(code)
        if perm is None:
            # No debería ocurrir: el upsert previo los habrá creado.
            click.secho(
                f"      ⚠️  '{code}' no existe en BD; salto", fg="yellow"
            )
            continue
        db.session.add(RolePermission(role_id=role.id, permission_id=perm.id))
        added += 1
    click.echo(f"   ✅ '{role.name}': bundle inicial → {added} permiso(s)")
    return added


@click.command("seed_permissions")
@with_appcontext
def seed_permissions():
    """Sincroniza catálogo de permisos y bundles iniciales (idempotente).

    Pasos:
    1. Upsert de permisos por `code`.
    2. Reporte de huérfanos en BD (no destructivo).
    3. Asegurar existencia de los 4 roles canónicos.
    4. Aplicar bundle inicial a cada rol — solo si el rol está vacío.
    """
    click.echo("🚀 SEED PERMISSIONS")

    # 1) + 2) Permisos
    created, updated, orphans = _upsert_permissions()
    click.echo(f"   📦 permissions: +{created} nuevos, ~{updated} actualizados")
    if orphans:
        click.secho(
            f"   ⚠️  permisos huérfanos en BD (no están en catálogo): {orphans}",
            fg="yellow",
        )
        click.echo("       → No se borran automáticamente. Revisar manualmente.")

    # flush para que los recién creados tengan id antes de mapear
    db.session.flush()

    # 3) Roles canónicos
    role_objs = {
        name: _ensure_role(name, description)
        for name, description in SYSTEM_ROLES.items()
    }

    # 4) Bundles — re-fetch del code→perm map para incluir los nuevos
    code_to_perm: dict[str, Permission] = {
        p.code: p for p in Permission.query.all()
    }
    for role_name, codes in BUNDLES.items():
        _apply_bundle(role_objs[role_name], codes, code_to_perm)

    db.session.commit()
    click.echo("🎉 SEED PERMISSIONS COMPLETADO")
