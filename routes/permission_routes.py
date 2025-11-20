from flask_smorest import Blueprint, abort
from flask.views import MethodView
from db import db
from models.permission import Permission
from models.role import Role
from schemas.permission_schema import PermissionSchema

blp = Blueprint("Permissions", "permissions", description="Gestión de permisos")

@blp.route("/permissions")
class PermissionList(MethodView):

    @blp.response(200, PermissionSchema(many=True))
    def get(self):
        """Obtener lista de permisos disponibles en el sistema."""
        return Permission.query.all()

    @blp.arguments(PermissionSchema)
    @blp.response(201, PermissionSchema)
    def post(self, permission_data):
        """Crear un nuevo permiso."""
        existing = Permission.query.filter_by(name=permission_data.name).first()
        if existing:
            abort(400, message="Ese permiso ya existe.")

        db.session.add(permission_data)
        db.session.commit()
        return permission_data


@blp.route("/permissions/<int:id>")
class PermissionById(MethodView):

    @blp.response(200, PermissionSchema)
    def get(self, id):
        """Obtener un permiso por ID."""
        permission = Permission.query.get_or_404(id)
        return permission

    @blp.arguments(PermissionSchema)
    @blp.response(200, PermissionSchema)
    def put(self, update_data, id):
        """Actualizar un permiso existente."""
        permission = Permission.query.get_or_404(id)

        # Validación: si cambia el nombre que no exista otro igual
        if update_data.name != permission.name:
            if Permission.query.filter_by(name=update_data.name).first():
                abort(400, message="Ya existe un permiso con ese nombre.")

        permission.name = update_data.name
        permission.description = update_data.description
        db.session.commit()

        return permission

    def delete(self, id):
        ""
@blp.route("/permissions/<int:perm_id>/assign-role/<int:role_id>", methods=["POST"])
class AssignPermissionToRole(MethodView):
    """Asigna un permiso a un rol."""
    def post(self, perm_id, role_id):
        permission = Permission.query.get_or_404(perm_id)
        role = Role.query.get_or_404(role_id)

        if permission in role.permissions:
            abort(400, message="Ese rol ya tiene este permiso asignado.")

        role.permissions.append(permission)
        db.session.commit()

        return {"message": f"Permiso '{permission.name}' asignado al rol '{role.name}'."}


@blp.route("/permissions/<int:perm_id>/remove-role/<int:role_id>", methods=["DELETE"])
class RemovePermissionFromRole(MethodView):
    """Remueve un permiso de un rol."""
    def delete(self, perm_id, role_id):
        permission = Permission.query.get_or_404(perm_id)
        role = Role.query.get_or_404(role_id)

        if permission not in role.permissions:
            abort(404, message="Ese rol no tiene este permiso asignado.")

        role.permissions.remove(permission)
        db.session.commit()

        return {"message": f"Permiso '{permission.name}' removido del rol '{role.name}'."}
