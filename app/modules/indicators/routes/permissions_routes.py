"""Endpoints read-only del catálogo de permisos (D1).

Sirve a la UI admin para renderizar checkboxes/listados de permisos. No
hay endpoints de edición aquí — la mutación llega en D2/D3.
"""
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required

from app.shared.models.permission import Permission
from app.shared.schemas.permission_schema import PermissionSchema
from app.utils.permissions import dual_required
from app.shared.permissions import PERM_ROLES_READ


blp = Blueprint(
    "permissions",
    "permissions",
    url_prefix="/permissions",
    description="Permissions catalog",
)


@blp.route("/")
class PermissionListResource(MethodView):

    @jwt_required()
    @dual_required(roles=("admin", "monitor"), perms=(PERM_ROLES_READ,))
    @blp.response(200, PermissionSchema(many=True))
    def get(self):
        """Lista el catálogo completo de permisos (ordenado por módulo + code)."""
        return (
            Permission.query
            .order_by(Permission.module.asc(), Permission.code.asc())
            .all()
        )
