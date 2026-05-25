"""Invariantes de seguridad operacional para RBAC (Bloque 11).

Estas funciones se usarán desde los servicios futuros de la UI admin
(crear/editar/eliminar roles, otorgar/revocar permisos). Centralizan
las reglas que protegen al sistema contra escenarios destructivos:

- Borrar un rol del sistema (`is_system=True`) — bloqueado.
- Borrar un rol que tiene usuarios asignados — bloqueado.
- Revocar permisos críticos al admin principal (`is_main_admin=True`).
- Que un actor reduzca sus propios permisos críticos (auto-degradación).

Cada función levanta `RBACInvariantError` si la operación está prohibida.
Los handlers de los endpoints traducen esto a HTTP 422 con mensaje.
"""
from typing import Iterable

from app.shared.models.role import Role
from app.shared.models.user import User
from app.shared.permissions import (
    PERM_USERS_MANAGE,
    PERM_USERS_MANAGE_PERMISSIONS,
    PERM_ROLES_MANAGE,
)


# Conjunto de permisos cuya pérdida deja al sistema sin operación
# administrativa básica. Si la operación reduce alguno de estos en el
# main admin (o en uno mismo), se bloquea.
CRITICAL_PERMISSIONS: frozenset[str] = frozenset({
    PERM_USERS_MANAGE,
    PERM_USERS_MANAGE_PERMISSIONS,
    PERM_ROLES_MANAGE,
})


class RBACInvariantError(Exception):
    """Operación viola un invariante de seguridad RBAC."""


def assert_can_delete_role(role: Role) -> None:
    """Lanza si el rol no se puede eliminar.

    Reglas:
    - Roles `is_system=True` no se eliminan desde la UI admin.
    - Roles con usuarios asignados no se eliminan (forzaría role_id = NULL
      o cascade, ambos peligrosos).
    """
    if role is None:
        raise RBACInvariantError("Rol no encontrado.")
    if role.is_system:
        raise RBACInvariantError(
            f"El rol '{role.name}' es del sistema y no puede eliminarse."
        )
    # `Role.users` es lazy=True; aceptamos el cost porque borrar un rol es
    # una operación poco frecuente y queremos un conteo confiable.
    if role.users:
        n = len(role.users)
        raise RBACInvariantError(
            f"El rol '{role.name}' tiene {n} usuario(s) asignado(s). "
            f"Reasigna esos usuarios antes de eliminar el rol."
        )


def assert_can_modify_user_permissions(
    actor: User,
    target: User,
    code: str,
    effect: str,
) -> None:
    """Lanza si la modificación de permisos viola algún invariante.

    `actor` realiza la operación, `target` la recibe.

    Reglas:
    1. No se puede revocar (effect='revoke') un permiso crítico al main admin.
    2. No se puede otorgar un revoke de permiso crítico a uno mismo (el actor
       no puede auto-degradarse).
    """
    if actor is None or target is None:
        raise RBACInvariantError("Actor o usuario objetivo no encontrado.")

    is_critical = code in CRITICAL_PERMISSIONS
    is_revoke = effect == "revoke"

    # Regla 1: protección del main admin
    if target.is_main_admin and is_critical and is_revoke:
        raise RBACInvariantError(
            f"No se puede revocar el permiso crítico '{code}' al admin principal."
        )

    # Regla 2: auto-degradación
    if actor.id == target.id and is_critical and is_revoke:
        raise RBACInvariantError(
            f"No puedes revocarte a ti mismo el permiso crítico '{code}'."
        )


def assert_can_change_user_role(
    actor: User,
    target: User,
    new_role: Role,
) -> None:
    """Lanza si el cambio de rol del usuario está bloqueado.

    Reglas:
    - No se puede cambiar el rol del main admin a algo distinto de 'admin'.
    - El actor no puede cambiarse a sí mismo a un rol no-admin (auto-degradación).
    """
    if actor is None or target is None or new_role is None:
        raise RBACInvariantError("Datos incompletos para cambiar rol.")

    if target.is_main_admin and new_role.name != "admin":
        raise RBACInvariantError(
            "No se puede cambiar el rol del admin principal a otro distinto de 'admin'."
        )

    if actor.id == target.id and new_role.name != "admin":
        # Solo admins pueden cambiar roles (es una operación protegida);
        # un admin que se cambia a sí mismo a no-admin perdería el control.
        raise RBACInvariantError(
            "No puedes cambiarte a ti mismo a un rol no-admin."
        )
