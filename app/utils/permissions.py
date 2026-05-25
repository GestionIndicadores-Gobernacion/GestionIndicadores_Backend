"""Capa central de autorización (Bloque 5 + adelanto del 9).

Esta capa coexiste con `role_required` durante toda la Fase A/B parcial.
El decorador legacy NO se modifica — sigue siendo válido y la fuente de
decisión activa en todos los endpoints existentes. Los nuevos helpers
(`require_permission`, `has_permission`, `current_user_permissions`) se
introducen aquí pero NO se aplican aún en ningún endpoint.

Diseño:
- Todos los lookups (User, permisos) están cacheados por request en
  `flask.g` para evitar N+1 cuando un mismo handler llama varios checks.
- `current_user_permissions()` prefiere el claim `permissions` del JWT;
  si el JWT no lo trae (sesiones viejas), hace fallback a BD eager-loading
  rol + permission_overrides en una sola pasada.
- Las relaciones nuevas (`Role.role_permissions`, `User.permission_overrides`)
  son `lazy='select'` deferred; el eager-loading explícito de abajo es la
  única vía por la que se cargan. Endpoints existentes NO las tocan.
"""
from functools import wraps
from typing import Iterable, Optional, Set

from flask import g, jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity
from sqlalchemy.orm import joinedload, selectinload

from app.shared.models.user import User
from app.shared.models.role import Role
from app.shared.models.role_permission import RolePermission
from app.shared.models.user_permission import UserPermission


# ─────────────────────────────────────────────────────────────────────────
# LEGACY — INTACTO. Cualquier cambio aquí rompe endpoints existentes.
# ─────────────────────────────────────────────────────────────────────────

def role_required(*allowed_roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            user = User.query.get(user_id)

            if not user or user.role.name not in allowed_roles:
                return jsonify({"message": "Forbidden"}), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────
# CURRENT USER — con cache por request.
# ─────────────────────────────────────────────────────────────────────────
# Sentinel para diferenciar "no cacheado" (None) de "cacheado como ausente".
_NOT_FOUND = object()


def _current_user_id() -> Optional[int]:
    """Devuelve el sub del JWT vigente, o None si no hay JWT/request."""
    try:
        ident = get_jwt_identity()
    except RuntimeError:
        return None
    if ident is None:
        return None
    try:
        return int(ident)
    except (TypeError, ValueError):
        return None


def _load_user_with_perms(user_id: int) -> Optional[User]:
    """Cargador con eager loading de rol + overrides, cacheado en `g`.

    Carga en a lo sumo 3 queries:
      - user JOIN role (joinedload)
      - role_permissions IN (...) JOIN permissions (selectinload + joined)
      - user_permissions IN (...) JOIN permissions (selectinload + joined)
    """
    cache_key = f"_perm_user_{user_id}"
    cached = getattr(g, cache_key, _NOT_FOUND)
    if cached is not _NOT_FOUND:
        return cached  # type: ignore[return-value]

    user = (
        User.query
        .options(
            joinedload(User.role)
              .selectinload(Role.role_permissions)
              .joinedload(RolePermission.permission),
            selectinload(User.permission_overrides)
              .joinedload(UserPermission.permission),
        )
        .filter(User.id == user_id)
        .first()
    )
    setattr(g, cache_key, user)
    return user


def current_user() -> Optional[User]:
    """User activo según el JWT vigente, eager-loaded y cacheado por request.

    Este helper es la versión centralizada (adelanto del Bloque 9). Los
    endpoints existentes siguen usando sus `_get_current_user` locales.
    """
    uid = _current_user_id()
    if uid is None:
        return None
    return _load_user_with_perms(uid)


def is_admin() -> bool:
    u = current_user()
    return bool(u and u.role and u.role.name == "admin")


def is_viewer() -> bool:
    u = current_user()
    return bool(u and u.role and u.role.name == "viewer")


# ─────────────────────────────────────────────────────────────────────────
# PERMISOS EFECTIVOS — role ∪ grants − revokes, cacheado por request.
# ─────────────────────────────────────────────────────────────────────────

def get_effective_permissions(user: Optional[User]) -> Set[str]:
    """Conjunto de permisos efectivos del usuario.

        permisos = permisos_del_rol(user.role) ∪ grants(user) − revokes(user)

    Cacheado por (request, user_id). Asume que `user` viene con sus
    relaciones cargadas (lo provee `_load_user_with_perms`). Si no, hace
    los SELECTs adicionales — el resultado sigue siendo correcto.
    """
    if user is None:
        return set()

    cache_key = f"_perm_set_{user.id}"
    cached = getattr(g, cache_key, _NOT_FOUND)
    if cached is not _NOT_FOUND:
        return cached  # type: ignore[return-value]

    from_role: Set[str] = set()
    if user.role is not None:
        for assoc in user.role.role_permissions:
            if assoc.permission is not None:
                from_role.add(assoc.permission.code)

    grants: Set[str] = set()
    revokes: Set[str] = set()
    for ov in user.permission_overrides:
        if ov.permission is None:
            continue
        if ov.effect == "grant":
            grants.add(ov.permission.code)
        elif ov.effect == "revoke":
            revokes.add(ov.permission.code)

    effective = (from_role | grants) - revokes
    setattr(g, cache_key, effective)
    return effective


def _jwt_permissions() -> Optional[Set[str]]:
    """Lee el claim `permissions` del JWT vigente, o None si no existe.

    Útil para evitar tocar BD cuando el cliente ya viene con un token
    fresco emitido en el Bloque 6+. Tolerante a JWTs viejos: devuelve None
    y deja que el caller haga fallback.
    """
    try:
        claims = get_jwt()
    except RuntimeError:
        return None
    perms = claims.get("permissions")
    if perms is None:
        return None
    if isinstance(perms, list):
        return set(perms)
    return None


def current_user_permissions() -> Set[str]:
    """Permisos efectivos del usuario activo.

    Estrategia:
    1. Si el JWT trae claim `permissions` (Bloque 6+), úsalo directamente.
    2. Si no (JWT viejo), carga el usuario eager y computa desde BD.

    Resultado cacheado en `g._perm_current_set_<uid>` para servir múltiples
    `has_permission` en una misma request sin re-leer JWT/BD. El sufijo
    por user_id evita colisiones cuando `g` se comparte entre contextos
    (relevante en tests con app_context session-scoped; en producción
    cada request tiene su propio app_context y el sufijo es solo defensa).
    """
    uid = _current_user_id()
    cache_key = f"_perm_current_set_{uid if uid is not None else 'none'}"
    cached = getattr(g, cache_key, _NOT_FOUND)
    if cached is not _NOT_FOUND:
        return cached  # type: ignore[return-value]

    jwt_perms = _jwt_permissions()
    if jwt_perms is not None:
        setattr(g, cache_key, jwt_perms)
        return jwt_perms

    # Fallback BD — compat con sesiones emitidas antes del Bloque 6.
    user = current_user()
    perms = get_effective_permissions(user)
    setattr(g, cache_key, perms)
    return perms


def has_permission(code: str) -> bool:
    """True si el usuario activo tiene el permiso."""
    return code in current_user_permissions()


def has_any_permission(codes: Iterable[str]) -> bool:
    owned = current_user_permissions()
    return any(c in owned for c in codes)


def has_all_permissions(codes: Iterable[str]) -> bool:
    owned = current_user_permissions()
    return all(c in owned for c in codes)


def dual_required(*, roles: tuple[str, ...] = (), perms: tuple[str, ...] = (),
                  all_perms: bool = False):
    """Decorador dual (Bloque 8-10) que compagina rol + permiso.

    Reemplaza el patrón "stack `@role_required(...) + @require_permission(...)`":
    centraliza ambas decisiones en un único punto y permite que el shadow
    mode (Bloque 12) detecte divergencias entre ambos criterios sin
    duplicar metadata por decorador.

    Política autoritativa durante Fase A/B parcial:
        Si `roles` se especifica → el check por rol es autoritativo (legacy).
        Si solo `perms` se especifica → el check por permiso decide.
    Esto garantiza que activar `dual_required` con ambos parámetros NO
    cambia el comportamiento existente; solo introduce telemetría sombra.
    """
    if not roles and not perms:
        raise ValueError("dual_required necesita al menos un role o un perm")

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            from flask import current_app, request as _flask_request

            # ── Decisión por rol (legacy) ────────────────────────────────
            user_id = None
            user = None
            try:
                user_id = get_jwt_identity()
                user = User.query.get(user_id) if user_id else None
            except RuntimeError:
                pass

            role_decision: bool
            if roles:
                role_decision = bool(
                    user and user.role and user.role.name in roles
                )
            else:
                # No hay roles que exigir → no veto desde lado rol.
                role_decision = True

            # ── Decisión por permisos (shadow / futuro autoritativo) ─────
            if perms:
                owned = current_user_permissions()
                if all_perms:
                    perm_decision = all(c in owned for c in perms)
                else:
                    perm_decision = any(c in owned for c in perms)
            else:
                perm_decision = True

            # ── Shadow mode (Bloque 12) ──────────────────────────────────
            if (
                current_app.config.get("PERM_SHADOW_MODE")
                and role_decision != perm_decision
            ):
                current_app.logger.warning(
                    "RBAC_SHADOW_DIVERGENCE endpoint=%s user_id=%s role=%s "
                    "role_allows=%s perm_allows=%s expected_roles=%s "
                    "expected_perms=%s",
                    getattr(_flask_request, "endpoint", None),
                    user_id,
                    user.role.name if user and user.role else None,
                    role_decision, perm_decision, roles, perms,
                )

            # ── Decisión efectiva ────────────────────────────────────────
            authoritative = role_decision if roles else perm_decision
            if not authoritative:
                return jsonify({"message": "Forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_permission(*codes: str, all_of: bool = False):
    """Decorador: exige permisos al endpoint.

    Convenciones:
    - Sin args es un error (no tiene sentido).
    - Por defecto (`all_of=False`) basta con tener UNO de los `codes`.
    - `all_of=True` exige todos.
    - Respuesta 403 + `{"message": "Forbidden"}` para consistencia con
      `role_required`. Esto evita que clientes existentes vean un shape
      distinto cuando se activen los chequeos en Bloques posteriores.

    Compatible para coexistir con `@role_required(...)` en el mismo
    endpoint (modo dual de los Bloques 8-10).
    """
    if not codes:
        raise ValueError("require_permission necesita al menos un code")

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            owned = current_user_permissions()
            if all_of:
                ok = all(c in owned for c in codes)
            else:
                ok = any(c in owned for c in codes)
            if not ok:
                return jsonify({"message": "Forbidden"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
