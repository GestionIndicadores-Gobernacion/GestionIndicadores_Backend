"""Handler de edición de permisos por rol (D2).

Operación soportada: PUT /roles/:id/permissions — bulk replace del set
de permisos asignados al rol. Granular grant/revoke queda fuera de
alcance (decisión de Stream A): los datasets de UI siempre envían el
estado deseado completo, lo que simplifica concurrencia y auditoría.

Reglas operacionales:
1. Validación atómica de input ANTES de tocar BD: si algún code no
   existe en `permissions`, devolvemos 404 y no se persiste nada.
2. Lockout: si el rol es `admin` y la operación quitaría algún
   `CRITICAL_PERMS`, devolvemos 403. Esto previene escenarios donde
   un admin se queda sin la capacidad de seguir administrando.
3. Diff calculado contra el estado actual del rol. Si el diff es vacío
   (no-op), commit transparente sin emitir AuditLog — evita ensuciar
   el log con eventos sin información.
4. AuditLog único por edición efectiva, con detail JSON estructurado.
   El JSON se serializa ordenado (`sort_keys=True`) para que los tests
   puedan compararlo sin parsear.
5. La invalidación del cache del JWT es lazy: los usuarios afectados
   verán los nuevos permisos en su próximo refresh. No tocamos `flask.g`
   ni el blocklist.
"""
import json
from typing import Optional

from flask import current_app

from app.core.extensions import db
from app.shared.models.audit_log import AuditLog
from app.shared.models.permission import Permission
from app.shared.models.role import Role
from app.shared.models.role_permission import RolePermission
from app.shared.permissions.catalog import CRITICAL_PERMS
from app.shared.schemas.permission_schema import PermissionSchema
from app.shared.schemas.role_schema import RoleDetailSchema


# Tipo de retorno: el handler devuelve siempre una 2-tupla (result, error).
# `error = (status_code, message)` o None.


def _serialize_response(role: Role, permissions: list[Permission]) -> dict:
    """Construye el mismo shape que devuelve el GET de /roles/:id/permissions.

    Permite al frontend hidratar tras un PUT exitoso sin necesidad de un
    refetch. El orden de permisos es (module, code), idéntico al GET.
    """
    sorted_perms = sorted(permissions, key=lambda p: (p.module, p.code))
    return {
        "role": RoleDetailSchema().dump(role),
        "permissions": PermissionSchema(many=True).dump(sorted_perms),
    }


class RolePermissionsHandler:
    """Servicio de bulk replace de permisos por rol."""

    @staticmethod
    def replace_permissions(
        role: Role,
        requested_codes: list[str],
        actor_id: int,
    ) -> tuple[Optional[dict], Optional[tuple[int, str]]]:
        """Reemplaza el set de permisos del rol.

        Returns:
            (result, None) en éxito: result tiene shape {role, permissions}.
            (None, (status_code, message)) en error.
        """
        # ── 1. Normalizar input (set, evitando duplicados accidentales) ─────
        unique_codes: set[str] = set(requested_codes or ())

        # ── 2. Validar que cada code exista en BD ───────────────────────────
        #    Un solo SELECT vs IN(...) — barato incluso para sets grandes.
        if unique_codes:
            found = Permission.query.filter(
                Permission.code.in_(unique_codes)
            ).all()
        else:
            found = []
        found_by_code: dict[str, Permission] = {p.code: p for p in found}
        missing = sorted(unique_codes - set(found_by_code.keys()))
        if missing:
            # Primer code desconocido para que el mensaje sea legible; la
            # lista completa la incluimos en el detail textual.
            unknown = missing[0]
            return None, (
                404,
                f"Permission code not found: {unknown}",
            )

        # ── 3. Estado actual del rol ────────────────────────────────────────
        current_assocs = list(role.role_permissions)
        current_codes: set[str] = {
            assoc.permission.code
            for assoc in current_assocs
            if assoc.permission is not None
        }
        target_codes = set(found_by_code.keys())

        added_codes = sorted(target_codes - current_codes)
        removed_codes = sorted(current_codes - target_codes)

        # ── 4. Lockout protection sobre el rol admin ────────────────────────
        if role.name == "admin":
            critical_being_removed = sorted(
                set(removed_codes) & CRITICAL_PERMS
            )
            if critical_being_removed:
                return None, (
                    403,
                    "Cannot remove critical permission(s) from admin role: "
                    + ", ".join(critical_being_removed),
                )

        # ── 5. No-op: commit sin tocar y sin auditar ────────────────────────
        if not added_codes and not removed_codes:
            return _serialize_response(role, [
                assoc.permission
                for assoc in current_assocs
                if assoc.permission is not None
            ]), None

        # ── 6. Aplicar diff ─────────────────────────────────────────────────
        # DELETEs primero, INSERTs después. Mismo db.session.commit() al final.
        if removed_codes:
            removed_perm_ids = [
                found_by_code_or_current(found_by_code, current_assocs, c)
                for c in removed_codes
            ]
            # Filtrar None (defensa contra orphans inesperados — no debería
            # pasar porque current_codes se computa desde assoc.permission).
            removed_perm_ids = [pid for pid in removed_perm_ids if pid is not None]
            if removed_perm_ids:
                (
                    RolePermission.query
                    .filter(RolePermission.role_id == role.id)
                    .filter(RolePermission.permission_id.in_(removed_perm_ids))
                    .delete(synchronize_session=False)
                )

        for code in added_codes:
            perm = found_by_code[code]
            db.session.add(RolePermission(
                role_id=role.id,
                permission_id=perm.id,
            ))

        # ── 7. AuditLog ─────────────────────────────────────────────────────
        before_count = len(current_codes)
        after_count = len(target_codes)
        shadow_active = bool(current_app.config.get("PERM_SHADOW_MODE"))
        detail_payload = {
            "role": {"id": role.id, "name": role.name},
            "added": added_codes,
            "removed": removed_codes,
            "before_count": before_count,
            "after_count": after_count,
            "shadow_mode_active": shadow_active,
        }
        db.session.add(AuditLog(
            user_id=actor_id,
            entity="role_permissions",
            entity_id=role.id,
            action="updated",
            detail=json.dumps(detail_payload, sort_keys=True),
        ))

        db.session.commit()

        # ── 8. Re-fetch del estado final para la respuesta ──────────────────
        db.session.refresh(role)
        final_perms = [
            assoc.permission
            for assoc in role.role_permissions
            if assoc.permission is not None
        ]
        return _serialize_response(role, final_perms), None


def found_by_code_or_current(
    found_by_code: dict[str, Permission],
    current_assocs: list[RolePermission],
    code: str,
) -> Optional[int]:
    """Resuelve el permission_id de un code.

    Para `added_codes` el code SIEMPRE existe en found_by_code (la
    validación previa lo garantiza). Para `removed_codes` el code puede
    no estar en found_by_code (no se solicitó en este request) — en ese
    caso lo buscamos en las asociaciones actuales.
    """
    perm = found_by_code.get(code)
    if perm is not None:
        return perm.id
    for assoc in current_assocs:
        if assoc.permission is not None and assoc.permission.code == code:
            return assoc.permission_id
    return None
