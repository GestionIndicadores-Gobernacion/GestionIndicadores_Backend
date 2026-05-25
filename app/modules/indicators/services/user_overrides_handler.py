"""Handler de edición de overrides por usuario (D3).

Operación soportada: PUT /users/:id/permissions/overrides — bulk replace
del set de overrides (grant/revoke) del target user. Granular POST/DELETE
queda fuera de alcance (decisión consciente del Stream A): la UI siempre
envía el estado deseado completo, lo que simplifica concurrencia, audit
y consistencia.

Reglas operacionales:

1. Validación atómica de input ANTES de tocar BD: si algún code no
   existe, si hay duplicados, o si el effect es inválido, devolvemos
   422/404 y NADA se persiste.

2. Lockouts (defensa en profundidad — múltiples reglas pueden activarse
   simultáneamente; al primer match devolvemos 403):
   - Self-lockout: un actor no puede revocar (effect='revoke') un
     CRITICAL_PERM a sí mismo.
   - Main-admin lockout: nadie puede revocar un CRITICAL_PERM al usuario
     marcado `is_main_admin=True`.
   - Admin colectivo: nadie puede revocar un CRITICAL_PERM a CUALQUIER
     usuario con rol 'admin' (cubre cuando dos admins se atacan entre sí,
     incluyendo escenarios sin main_admin).

3. Diff calculado contra el estado actual del target. Tres conjuntos:
   - added:   permission_codes que NO tenían override y ahora tienen uno.
   - removed: permission_codes que SÍ tenían override y dejan de tenerlo.
   - changed: permission_codes cuyo `effect` cambió (grant↔revoke).

   Si los 3 están vacíos (no-op semántico), commit transparente sin
   emitir AuditLog — evita ensuciar el log con eventos sin información.

4. AuditLog único por edición efectiva, con detail JSON estructurado y
   serializado con sort_keys=True para que los diffs en CI sean estables.

5. Validación adicional: NO se puede revocar un permiso que el rol del
   target NO concede — un revoke huérfano sería ruido. Se devuelve 422
   con mensaje que nombra el code y el rol.

6. Cache invalidation: ANTES de re-leer permisos efectivos para la
   respuesta, se purga `flask.g._perm_set_<target_user_id>` para que el
   set devuelto refleje el commit recién hecho y no un valor cacheado
   por código corriente en la misma request.
"""
import json
from datetime import datetime, timezone
from typing import Optional

from flask import current_app, g

from app.core.extensions import db
from app.shared.models.audit_log import AuditLog
from app.shared.models.permission import Permission
from app.shared.models.user import User
from app.shared.models.user_permission import UserPermission
from app.shared.permissions.catalog import CRITICAL_PERMS
from app.shared.schemas.user_permission_schema import (
    UserPermissionOverrideSchema,
    UserPermissionsViewSchema,
)
from app.utils.permissions import get_permission_breakdown


# El handler devuelve siempre una 2-tupla (result, error).
# `error = (status_code, message)` o None.


VALID_EFFECTS = ("grant", "revoke")


def _build_permissions_view(target_user: User) -> dict:
    """Construye el payload `UserPermissionsViewSchema`.

    Recalcula el breakdown desde cero (no toca flask.g) para reflejar el
    estado post-commit. Se hace antes de Marshmallow dump para que la
    forma JSON sea consistente con el GET D1.
    """
    breakdown = get_permission_breakdown(target_user)
    payload = {
        "user": {
            "id": target_user.id,
            "email": target_user.email,
            "role": (
                {"id": target_user.role.id, "name": target_user.role.name}
                if target_user.role else None
            ),
        },
        "from_role": sorted(breakdown["from_role"]),
        "grants":    sorted(breakdown["grants"]),
        "revokes":   sorted(breakdown["revokes"]),
        "effective": sorted(breakdown["effective"]),
    }
    return UserPermissionsViewSchema().dump(payload)


def _serialize_overrides(target_user_id: int) -> list[dict]:
    """Devuelve los overrides del target ordenados por (module, code).

    Re-fetch tras el commit para que la lista refleje exactamente lo
    persistido. Mismo orden que el GET D1.
    """
    from sqlalchemy.orm import joinedload
    overrides = (
        UserPermission.query
        .options(
            joinedload(UserPermission.permission),
            joinedload(UserPermission.granted_by_user),
        )
        .filter(UserPermission.user_id == target_user_id)
        .all()
    )
    overrides.sort(
        key=lambda o: (
            o.permission.module if o.permission else "",
            o.permission.code if o.permission else "",
        )
    )
    return UserPermissionOverrideSchema(many=True).dump(overrides)


def _build_response(target_user: User) -> dict:
    """Compone el shape `{overrides, permissions}` que devuelve el PUT.

    El frontend usa este shape para hidratar el drawer sin refetch tras
    el PUT.
    """
    return {
        "overrides": _serialize_overrides(target_user.id),
        "permissions": _build_permissions_view(target_user),
    }


class UserOverridesHandler:
    """Servicio de bulk replace de overrides (grant/revoke) por usuario."""

    @staticmethod
    def replace_overrides(
        target_user: User,
        actor: User,
        requested_overrides: list[dict],
    ) -> tuple[Optional[dict], Optional[tuple[int, str]]]:
        """Reemplaza el set de overrides del `target_user`.

        Args:
            target_user: Usuario sobre quien se aplican los overrides.
            actor: Usuario que ejecuta la edición (para audit/granted_by).
            requested_overrides: Lista de dicts con shape
                `{"permission_code": "...", "effect": "grant"|"revoke"}`.

        Returns:
            (result, None) en éxito: result tiene shape
                `{overrides, permissions}`.
            (None, (status_code, message)) en error.
        """
        # ── 1. Normalizar / validar effect ───────────────────────────────
        if not isinstance(requested_overrides, list):
            return None, (422, "overrides must be a list")

        for entry in requested_overrides:
            if not isinstance(entry, dict):
                return None, (422, "each override must be an object")
            if "permission_code" not in entry or "effect" not in entry:
                return None, (
                    422,
                    "each override needs 'permission_code' and 'effect'",
                )
            if entry["effect"] not in VALID_EFFECTS:
                return None, (
                    422,
                    f"effect inválido: '{entry['effect']}'. "
                    f"Debe ser 'grant' o 'revoke'.",
                )

        # ── 2. Detectar duplicados de permission_code ─────────────────────
        codes_seen: set[str] = set()
        for entry in requested_overrides:
            code = entry["permission_code"]
            if code in codes_seen:
                return None, (
                    422,
                    f"permission_code duplicado en el body: '{code}'.",
                )
            codes_seen.add(code)

        # ── 3. Validar que cada permission_code existe en BD ──────────────
        requested_codes = {e["permission_code"] for e in requested_overrides}
        if requested_codes:
            found = Permission.query.filter(
                Permission.code.in_(requested_codes)
            ).all()
        else:
            found = []
        found_by_code: dict[str, Permission] = {p.code: p for p in found}
        missing = sorted(requested_codes - set(found_by_code.keys()))
        if missing:
            # Primer code desconocido para legibilidad — el frontend ya
            # validó codes contra el catálogo, ver uno suele ser suficiente.
            unknown = missing[0]
            return None, (404, f"Permission code not found: {unknown}")

        # ── 4. Validar que revoke se aplica a un perm que el rol da ──────
        # Un revoke sobre algo que el rol del target no tiene es semántica
        # vacía — bloqueamos para evitar overrides "muertos". Calculamos
        # el set del rol con el helper que NO toca flask.g.
        breakdown_before = get_permission_breakdown(target_user)
        from_role_codes: set[str] = breakdown_before["from_role"]
        for entry in requested_overrides:
            if entry["effect"] == "revoke":
                code = entry["permission_code"]
                if code not in from_role_codes:
                    role_name = (
                        target_user.role.name if target_user.role else "(sin rol)"
                    )
                    return None, (
                        422,
                        f"revoke inválido: el rol '{role_name}' no tiene "
                        f"'{code}'.",
                    )

        # ── 5. Lockouts (defensa en profundidad: chequeamos las 3 reglas) ─
        # Aplican SOLO a revokes de permisos críticos. Granting un crítico
        # a otro es escalación intencional — se permite.
        is_target_main_admin = bool(target_user.is_main_admin)
        is_target_admin_role = (
            target_user.role is not None and target_user.role.name == "admin"
        )
        is_self = (actor.id == target_user.id)

        for entry in requested_overrides:
            if entry["effect"] != "revoke":
                continue
            code = entry["permission_code"]
            if code not in CRITICAL_PERMS:
                continue

            # Regla 1: self-lockout
            if is_self:
                return None, (
                    403,
                    f"No puedes revocarte a ti mismo el permiso crítico "
                    f"'{code}'.",
                )

            # Regla 2: main-admin lockout
            if is_target_main_admin:
                return None, (
                    403,
                    f"No se puede revocar el permiso crítico '{code}' al "
                    f"admin principal.",
                )

            # Regla 3: admin colectivo
            if is_target_admin_role:
                return None, (
                    403,
                    f"No se puede revocar el permiso crítico '{code}' a un "
                    f"usuario con rol 'admin'.",
                )

        # ── 6. Snapshot del estado actual de overrides del target ─────────
        current_overrides = (
            UserPermission.query
            .filter(UserPermission.user_id == target_user.id)
            .all()
        )
        current_by_code: dict[str, UserPermission] = {}
        for ov in current_overrides:
            # Si por inconsistencia ov.permission no estuviera cargado,
            # haríamos un lookup adicional — pero el relationship
            # `lazy='joined'` lo cubre.
            if ov.permission is not None:
                current_by_code[ov.permission.code] = ov

        # ── 7. Calcular diff: added / removed / changed ───────────────────
        requested_by_code: dict[str, str] = {
            e["permission_code"]: e["effect"] for e in requested_overrides
        }
        added: list[dict] = []
        changed: list[dict] = []
        for code, effect in sorted(requested_by_code.items()):
            existing = current_by_code.get(code)
            if existing is None:
                added.append({"permission_code": code, "effect": effect})
            elif existing.effect != effect:
                changed.append({
                    "permission_code": code,
                    "from": existing.effect,
                    "to": effect,
                })

        removed: list[dict] = []
        for code in sorted(current_by_code.keys() - requested_by_code.keys()):
            existing = current_by_code[code]
            removed.append({
                "permission_code": code,
                "effect": existing.effect,
            })

        # ── 8. No-op: nada que persistir ni auditar ───────────────────────
        if not added and not removed and not changed:
            # Invalidamos el cache defensivamente — en este path no debería
            # haber cambiado nada, pero la llamada es barata y evita lecturas
            # rancias en tests que comparten request_context.
            g.pop(f"_perm_set_{target_user.id}", None)
            return _build_response(target_user), None

        # ── 9. Aplicar diff (DELETE + UPDATE + INSERT en una transacción) ─
        now = datetime.now(timezone.utc)

        # 9a. DELETE de overrides removidos.
        if removed:
            removed_perm_ids = [
                current_by_code[d["permission_code"]].permission_id
                for d in removed
            ]
            (
                UserPermission.query
                .filter(UserPermission.user_id == target_user.id)
                .filter(UserPermission.permission_id.in_(removed_perm_ids))
                .delete(synchronize_session="fetch")
            )

        # 9b. UPDATE in-place de overrides que cambiaron effect.
        #    Mantiene la fila (mismo PK) — preserva granted_at original NO,
        #    lo refrescamos junto con granted_by porque el cambio merece
        #    quedar registrado en metadata.
        for diff in changed:
            ov = current_by_code[diff["permission_code"]]
            ov.effect = diff["to"]
            ov.granted_by = actor.id
            ov.granted_at = now

        # 9c. INSERT de nuevos overrides.
        for diff in added:
            perm = found_by_code[diff["permission_code"]]
            db.session.add(UserPermission(
                user_id=target_user.id,
                permission_id=perm.id,
                effect=diff["effect"],
                granted_by=actor.id,
                granted_at=now,
            ))

        # ── 10. AuditLog ─────────────────────────────────────────────────
        shadow_active = bool(current_app.config.get("PERM_SHADOW_MODE"))
        detail_payload = {
            "target_user": {
                "id": target_user.id,
                "email": target_user.email,
            },
            "added":   added,
            "removed": removed,
            "changed": changed,
            "shadow_mode_active": shadow_active,
        }
        db.session.add(AuditLog(
            user_id=actor.id,
            entity="user_permission_overrides",
            entity_id=target_user.id,
            action="updated",
            detail=json.dumps(detail_payload, sort_keys=True),
        ))

        db.session.commit()

        # ── 11. Cache invalidation (CRÍTICO) ─────────────────────────────
        # `get_effective_permissions` cachea por (request, user_id) en
        # `flask.g._perm_set_<uid>`. Si algo en esta misma request leyó
        # el set ANTES del commit, la entrada cacheada es rancia. Si la
        # leemos AHORA para componer la respuesta sin purgar primero,
        # devolveríamos el set pre-cambio. Por eso forzamos invalidación.
        g.pop(f"_perm_set_{target_user.id}", None)
        # También invalidamos `_perm_user_<uid>` por consistencia: aunque
        # `get_permission_breakdown` no toca este cache, otros consumidores
        # en la misma request podrían leerlo y recibir un User con
        # permission_overrides stale.
        g.pop(f"_perm_user_{target_user.id}", None)

        # ── 12. Re-fetch del estado final para la respuesta ──────────────
        # `db.session.refresh(target_user)` recarga columnas pero no
        # relationships listas; expirar fuerza relectura en el siguiente
        # acceso. Esto garantiza que `target_user.permission_overrides`
        # devuelva el set actualizado.
        db.session.expire(target_user)
        # Re-cargar el target con el eager loading que necesita el helper
        # de breakdown — sin esto, `target_user.role.role_permissions` y
        # `target_user.permission_overrides` se cargan vía lazy='select',
        # lo cual sigue siendo correcto pero menos eficiente.
        from sqlalchemy.orm import joinedload, selectinload
        from app.shared.models.role import Role as _Role
        from app.shared.models.role_permission import RolePermission as _RP
        reloaded = (
            User.query
            .options(
                joinedload(User.role)
                  .selectinload(_Role.role_permissions)
                  .joinedload(_RP.permission),
                selectinload(User.permission_overrides)
                  .joinedload(UserPermission.permission),
            )
            .filter(User.id == target_user.id)
            .first()
        )
        return _build_response(reloaded), None
