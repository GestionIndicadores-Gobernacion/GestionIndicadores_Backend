"""Comando one-shot: limpia los permisos `action_plans.report_activity` y
`action_plans.add_evidence` de los roles `monitor` y `editor`.

Contexto: Tras migrar `_can_report_activity` y `_can_add_evidence` a la
política `is_responsible OR has_permission(PERM)` (override granular), los
bundles default de `seed_permissions.py` ya no incluyen esos permisos para
monitor/editor. Pero `seed_permissions` solo aplica bundles a roles vacíos,
así que en instalaciones ya seeded los permisos siguen colgados en BD.

Este comando elimina esas asociaciones role↔permission para dejar la BD en
línea con el nuevo default. No toca:
  - El rol `admin` (debe mantener ambos permisos por su bundle "todos").
  - Los `user_permission_overrides` (grants/revokes explícitos hechos vía UI).

Idempotente: correrlo dos veces es seguro. Se puede correr con --dry-run
para previsualizar sin aplicar.
"""
import click
from flask.cli import with_appcontext

from app.core.extensions import db
from app.shared.models.role import Role
from app.shared.models.role_permission import RolePermission
from app.shared.models.permission import Permission
from app.shared.permissions import (
    PERM_ACTION_PLANS_REPORT_ACTIVITY,
    PERM_ACTION_PLANS_ADD_EVIDENCE,
)


# Permisos a limpiar y roles afectados.
_TARGET_PERMS = (
    PERM_ACTION_PLANS_REPORT_ACTIVITY,
    PERM_ACTION_PLANS_ADD_EVIDENCE,
)
_TARGET_ROLES = ("monitor", "editor")


@click.command("cleanup-action-plans-overrides")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Muestra qué se eliminaría sin aplicar cambios.",
)
@with_appcontext
def cleanup_action_plans_overrides(dry_run: bool):
    """Quita REPORT_ACTIVITY y ADD_EVIDENCE de los roles monitor/editor."""
    # Sin emojis: stdout de Windows (cp1252) no los soporta y aborta el
    # comando con UnicodeEncodeError. Mismo motivo que el fix histórico
    # `214d99e fix: remove debug print that breaks flask run on Windows cp1252`.
    click.echo("CLEANUP action_plans overrides (monitor + editor)")
    if dry_run:
        click.secho("   (modo dry-run: no se aplicaran cambios)", fg="yellow")

    # Resolver permisos y roles. Si algo falta, mejor abortar que asumir.
    perms_by_code = {
        p.code: p for p in Permission.query.filter(Permission.code.in_(_TARGET_PERMS)).all()
    }
    missing_perms = [c for c in _TARGET_PERMS if c not in perms_by_code]
    if missing_perms:
        click.secho(
            f"   [ERROR] permisos no encontrados en BD: {missing_perms}. "
            "Corre `flask seed_permissions` primero.",
            fg="red",
        )
        return

    perm_ids = {p.id for p in perms_by_code.values()}
    code_by_perm_id = {p.id: code for code, p in perms_by_code.items()}

    roles_by_name = {
        r.name: r for r in Role.query.filter(Role.name.in_(_TARGET_ROLES)).all()
    }
    missing_roles = [n for n in _TARGET_ROLES if n not in roles_by_name]
    if missing_roles:
        click.secho(
            f"   [INFO] roles no encontrados (se omiten): {missing_roles}",
            fg="yellow",
        )

    total_removed = 0
    for role_name in _TARGET_ROLES:
        role = roles_by_name.get(role_name)
        if role is None:
            continue

        # Buscar las RolePermission a borrar (solo las que matchean los target).
        to_remove = (
            RolePermission.query
            .filter(RolePermission.role_id == role.id)
            .filter(RolePermission.permission_id.in_(perm_ids))
            .all()
        )

        if not to_remove:
            click.echo(f"   [SKIP] '{role_name}': ya esta limpio (nada que hacer)")
            continue

        codes = sorted(code_by_perm_id[rp.permission_id] for rp in to_remove)
        click.echo(f"   [APPLY] '{role_name}': eliminando {len(to_remove)} permiso(s) -> {codes}")
        if not dry_run:
            for rp in to_remove:
                db.session.delete(rp)
        total_removed += len(to_remove)

    if dry_run:
        click.echo(f"Total que se eliminaria: {total_removed} (dry-run, no aplicado)")
        return

    if total_removed == 0:
        click.echo("Nada que limpiar - BD ya alineada con el nuevo default.")
        return

    db.session.commit()
    click.secho(
        f"CLEANUP COMPLETADO - {total_removed} asociacion(es) role-permission eliminada(s).",
        fg="green",
    )
    click.echo(
        "   [INFO] user_permission_overrides NO fueron tocados; si queres revisar "
        "grants explicitos por usuario, hacelo desde la UI admin."
    )
