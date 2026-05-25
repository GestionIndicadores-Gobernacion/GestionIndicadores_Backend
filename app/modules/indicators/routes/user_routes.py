from flask import jsonify, request
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required
from sqlalchemy.orm import joinedload, selectinload

from app.modules.indicators.services.user_handler import UserHandler
from app.modules.indicators.services.user_overrides_handler import (
    UserOverridesHandler,
)
from app.shared.schemas.user_schema import UserSchema
from app.shared.schemas.user_permission_schema import (
    UserPermissionsViewSchema,
    UserPermissionOverrideSchema,
    UserOverridesUpdateSchema,
)
from app.shared.models.user import User
from app.shared.models.role import Role
from app.shared.models.role_permission import RolePermission
from app.shared.models.user_component import UserComponent
from app.shared.models.user_permission import UserPermission
from app.utils.permissions import (
    role_required,
    dual_required,
    get_permission_breakdown,
)
from app.utils.pagination import get_pagination_params, paginate_query, envelope
from app.shared.permissions import (
    PERM_USERS_MANAGE,
    PERM_USERS_ASSIGN_COMPONENTS,
    PERM_USERS_READ_PERMISSIONS,
    PERM_USERS_MANAGE_PERMISSIONS,
)


def _basic_user_dump(users):
    """Proyección mínima (id, first_name, last_name) para roles no privilegiados.
    Suficiente para poblar selects de "responsable" sin filtrar email,
    role ni component_assignments.
    """
    return [
        {"id": u.id, "first_name": u.first_name, "last_name": u.last_name}
        for u in users
    ]

blp = Blueprint(
    "users",
    "users",
    url_prefix="/users",
    description="User management"
)


# ── CRUD base ────────────────────────────────────────────────────────────────

from flask_jwt_extended import get_jwt_identity

@blp.route("/me")
class UserMeResource(MethodView):

    @jwt_required()
    @blp.response(200, UserSchema)
    def get(self):
        user_id = get_jwt_identity()
        user = UserHandler.get_by_id(int(user_id))
        if not user:
            return {"message": "User not found"}, 404
        return user


@blp.route("/me/permissions")
class UserMePermissionsResource(MethodView):
    """Endpoint dedicado de permisos efectivos del usuario activo.

    Aditivo: el cliente ya puede leerlos del JWT o de /users/me. Útil
    para refrescar el set tras un cambio admin sin esperar a que el
    JWT expire y se reemita.
    """

    @jwt_required()
    def get(self):
        from app.utils.permissions import current_user, current_user_permissions
        user = current_user()
        if not user:
            return {"message": "User not found"}, 404
        return jsonify({
            "role": {
                "id": user.role.id if user.role else None,
                "name": user.role.name if user.role else None,
            },
            "permissions": sorted(current_user_permissions()),
        }), 200
    
@blp.route("/")
class UserListResource(MethodView):

    @jwt_required()
    def get(self):
        """
        GET /users/[?limit=&offset=]

        Acceso:
          - admin / monitor → datos completos (UserSchema).
          - editor          → proyección básica (id + nombre) para poblar
                              selects de responsable en el Plan de Acción.
          - viewer          → 403.

        - Sin parámetros → lista completa (retrocompatible).
        - Con `limit`/`offset` → envelope `{ items, total, limit, offset }`.
        """
        current_id = int(get_jwt_identity())
        current = UserHandler.get_by_id(current_id)
        role_name = current.role.name if current and current.role else None
        if role_name not in ("admin", "monitor", "editor"):
            return jsonify({"message": "Forbidden"}), 403

        is_privileged = role_name in ("admin", "monitor")
        dump = (lambda items: UserSchema(many=True).dump(items)) if is_privileged else _basic_user_dump

        query = User.query.order_by(User.created_at.desc())

        # Filtro opcional: ?component_id=N → solo usuarios con ese componente
        # asignado en user_components. Útil para poblar el select de
        # "Responsables" en el modal de Plan de Acción según el componente
        # elegido.
        component_id = request.args.get("component_id", type=int)
        if component_id:
            query = (
                query
                .join(UserComponent, UserComponent.user_id == User.id)
                .filter(UserComponent.component_id == component_id)
                .distinct()
            )

        paginated, limit, offset = get_pagination_params()
        if not paginated:
            return jsonify(dump(query.all())), 200
        items, total = paginate_query(query, limit, offset)
        return jsonify(envelope(dump(items), total, limit, offset)), 200

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_USERS_MANAGE,))
    @blp.arguments(UserSchema)
    @blp.response(201, UserSchema)
    def post(self, data):
        """Crear usuario. Puede incluir component_ids: [1,2,3]"""
        user, errors = UserHandler.create(data)
        if errors:
            return {"errors": errors}, 400
        return user


@blp.route("/<int:user_id>")
class UserResource(MethodView):

    @jwt_required()
    @blp.response(200, UserSchema)
    def get(self, user_id):
        # Solo admin/monitor pueden ver cualquier usuario; el resto
        # solamente su propio perfil (/users/me es la ruta canónica).
        current_id = int(get_jwt_identity())
        current = UserHandler.get_by_id(current_id)
        is_privileged = bool(
            current and current.role and current.role.name in ("admin", "monitor")
        )
        if not is_privileged and current_id != user_id:
            return {"message": "Forbidden"}, 403

        user = UserHandler.get_by_id(user_id)
        if not user:
            return {"message": "User not found"}, 404
        return user

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_USERS_MANAGE,))
    @blp.arguments(UserSchema(partial=True))
    @blp.response(200, UserSchema)
    def put(self, data, user_id):
        """Editar usuario. Si incluye component_ids, reemplaza todas las asignaciones."""
        user = UserHandler.get_by_id(user_id)
        if not user:
            return {"message": "User not found"}, 404
        return UserHandler.update(user, data)

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_USERS_MANAGE,))
    @blp.response(204)
    def delete(self, user_id):
        user = UserHandler.get_by_id(user_id)
        if not user:
            return {"message": "User not found"}, 404
        UserHandler.delete(user)


# ── Asignaciones de componentes ──────────────────────────────────────────────

@blp.route("/<int:user_id>/components/<int:component_id>")
class UserComponentResource(MethodView):

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_USERS_ASSIGN_COMPONENTS,))
    @blp.response(201)
    def post(self, user_id, component_id):
        """Asignar un componente a un usuario."""
        user = UserHandler.get_by_id(user_id)
        if not user:
            return {"message": "User not found"}, 404

        uc, error = UserHandler.assign_component(user_id, component_id)
        if error:
            return {"message": error}, 400
        return {"message": "Component assigned", "user_id": user_id, "component_id": component_id}

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_USERS_ASSIGN_COMPONENTS,))
    @blp.response(204)
    def delete(self, user_id, component_id):
        """Quitar un componente de un usuario."""
        removed = UserHandler.remove_component(user_id, component_id)
        if not removed:
            return {"message": "Assignment not found"}, 404


# ── Permisos efectivos / overrides (D1, read-only) ─────────────────────────

def _load_user_for_perm_inspection(user_id: int):
    """Carga un usuario con todas las relaciones necesarias para inspeccionar
    sus permisos en una sola pasada (eager loading).
    """
    return (
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


@blp.route("/<int:user_id>/permissions")
class UserPermissionsAdminResource(MethodView):
    """Permisos efectivos de un usuario, vistos por un admin (D1).

    Devuelve el desglose `{from_role, grants, revokes, effective}` para
    diagnóstico de la matriz de permisos del usuario. No hace login al
    target — siempre se ejecuta en el contexto del JWT del admin actual.
    """

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_USERS_READ_PERMISSIONS,))
    def get(self, user_id):
        user = _load_user_for_perm_inspection(user_id)
        if not user:
            return {"message": "User not found"}, 404

        breakdown = get_permission_breakdown(user)
        payload = {
            "user": {
                "id": user.id,
                "email": user.email,
                "role": (
                    {"id": user.role.id, "name": user.role.name}
                    if user.role else None
                ),
            },
            "from_role": sorted(breakdown["from_role"]),
            "grants":    sorted(breakdown["grants"]),
            "revokes":   sorted(breakdown["revokes"]),
            "effective": sorted(breakdown["effective"]),
        }
        return jsonify(UserPermissionsViewSchema().dump(payload)), 200


@blp.route("/<int:user_id>/permissions/overrides")
class UserPermissionOverridesResource(MethodView):
    """Overrides directos (grant/revoke) de un usuario.

    - GET (D1, read-only): lista UserPermission del target ordenados por
      (módulo, code). Acceso: admin con `users.read_permissions`.
    - PUT (D3): bulk replace del set de overrides. Acceso: admin con
      `users.manage_permissions`. El handler valida lockouts (self,
      main-admin, admin-colectivo) y emite AuditLog.
    """

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_USERS_READ_PERMISSIONS,))
    @blp.response(200, UserPermissionOverrideSchema(many=True))
    def get(self, user_id):
        # 404 si el usuario no existe.
        target = User.query.get(user_id)
        if not target:
            return {"message": "User not found"}, 404

        overrides = (
            UserPermission.query
            .options(
                joinedload(UserPermission.permission),
                joinedload(UserPermission.granted_by_user),
            )
            .filter(UserPermission.user_id == user_id)
            .all()
        )
        # Orden estable por (permission.module, permission.code) en Python
        # — la cláusula ORDER BY en SQL requiere un JOIN extra y el set
        # de overrides es pequeño, así que ordenamos en memoria.
        overrides.sort(
            key=lambda o: (
                o.permission.module if o.permission else "",
                o.permission.code if o.permission else "",
            )
        )
        return overrides

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_USERS_MANAGE_PERMISSIONS,))
    @blp.arguments(UserOverridesUpdateSchema)
    def put(self, payload, user_id):
        """Bulk replace de overrides del usuario (D3).

        Body: `{"overrides": [{permission_code, effect}, ...]}` — el set
        completo de overrides que quedará persistido. Devuelve
        `{overrides, permissions}` para hidratar el drawer sin refetch.
        """
        target = _load_user_for_perm_inspection(user_id)
        if not target:
            return jsonify({"message": "User not found"}), 404

        try:
            actor_id = int(get_jwt_identity())
        except (TypeError, ValueError):
            return jsonify({"message": "Invalid token identity"}), 401
        actor = User.query.get(actor_id)
        if not actor:
            return jsonify({"message": "Actor not found"}), 401

        result, error = UserOverridesHandler.replace_overrides(
            target_user=target,
            actor=actor,
            requested_overrides=payload.get("overrides", []),
        )
        if error is not None:
            status, msg = error
            return jsonify({"message": msg}), status
        return jsonify(result), 200