from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.orm import joinedload, selectinload

from app.modules.indicators.services.role_handler import RoleHandler
from app.modules.indicators.services.role_permissions_handler import (
    RolePermissionsHandler,
)
from app.shared.models.role import Role
from app.shared.models.role_permission import RolePermission
from app.shared.schemas.role_schema import (
    RoleSchema,
    RoleDetailSchema,
    RolePermissionsUpdateSchema,
)
from app.shared.schemas.permission_schema import PermissionSchema
from app.utils.permissions import dual_required
from app.shared.permissions import PERM_ROLES_READ, PERM_ROLES_MANAGE

blp = Blueprint(
    "roles",
    "roles",
    url_prefix="/roles",
    description="Roles"
)


@blp.route("/")
class RoleListResource(MethodView):

    @jwt_required()
    @dual_required(roles=("admin", "monitor"), perms=(PERM_ROLES_READ,))
    @blp.response(200, RoleDetailSchema(many=True))
    def get(self):
        return (
            Role.query
            .options(
                selectinload(Role.role_permissions),
                selectinload(Role.users),
            )
            .order_by(Role.id.asc())
            .all()
        )


@blp.route("/<int:role_id>")
class RoleResource(MethodView):

    @jwt_required()
    @dual_required(roles=("admin", "monitor"), perms=(PERM_ROLES_READ,))
    @blp.response(200, RoleSchema)
    def get(self, role_id):
        role = RoleHandler.get_by_id(role_id)
        if not role:
            return {"message": "Role not found"}, 404
        return role


@blp.route("/<int:role_id>/permissions")
class RolePermissionsResource(MethodView):
    """Detalle del rol + sus permisos asignados.

    - GET (D1, read-only): renderiza la matriz de permisos.
    - PUT (D2): bulk replace del set asignado; solo admin con
      `roles.manage`. El handler valida lockout para el rol admin.
    """

    @jwt_required()
    @dual_required(roles=("admin", "monitor"), perms=(PERM_ROLES_READ,))
    def get(self, role_id):
        role = (
            Role.query
            .options(
                selectinload(Role.role_permissions)
                  .joinedload(RolePermission.permission),
                selectinload(Role.users),
            )
            .filter(Role.id == role_id)
            .first()
        )
        if not role:
            return {"message": "Role not found"}, 404

        permissions = sorted(
            (
                assoc.permission for assoc in role.role_permissions
                if assoc.permission is not None
            ),
            key=lambda p: (p.module, p.code),
        )
        return jsonify({
            "role": RoleDetailSchema().dump(role),
            "permissions": PermissionSchema(many=True).dump(permissions),
        }), 200

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_ROLES_MANAGE,))
    @blp.arguments(RolePermissionsUpdateSchema)
    def put(self, payload, role_id):
        """Bulk replace del set de permisos asignados al rol.

        Body: `{"permission_codes": ["...", "..."]}` — el rol queda con
        EXACTAMENTE ese set tras la operación. Si algún code no existe,
        devolvemos 404. Si la operación rompería al rol admin (al quitar
        un `CRITICAL_PERM`), devolvemos 403.

        Devuelve el mismo shape que el GET para que el cliente hidrate
        sin necesidad de un refetch.
        """
        role = (
            Role.query
            .options(
                selectinload(Role.role_permissions)
                  .joinedload(RolePermission.permission),
                selectinload(Role.users),
            )
            .filter(Role.id == role_id)
            .first()
        )
        if not role:
            return jsonify({"message": "Role not found"}), 404

        try:
            actor_id = int(get_jwt_identity())
        except (TypeError, ValueError):
            actor_id = None

        result, error = RolePermissionsHandler.replace_permissions(
            role=role,
            requested_codes=payload.get("permission_codes", []),
            actor_id=actor_id,
        )
        if error is not None:
            status, msg = error
            return jsonify({"message": msg}), status
        return jsonify(result), 200
