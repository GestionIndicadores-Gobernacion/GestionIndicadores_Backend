from flask_smorest import Blueprint, abort
from flask.views import MethodView
from extensions import db
from models.permission import Permission
from models.role import Role
from schemas.permission_schema import PermissionSchema

blp = Blueprint("Permissions", "permissions", description="Gestión de permisos")


# ---------------------------------------------------------
# LISTAR Y CREAR PERMISOS
# ---------------------------------------------------------
@blp.route("/permissions")
class PermissionList(MethodView):

    @blp.response(200, PermissionSchema(many=True))
    def get(self):
        """Obtener lista de permisos."""
        return Permission.query.all()

    @blp.arguments(PermissionSchema)
    @blp.response(201, PermissionSchema)
    def post(self, permission_data):
        """Crear un nuevo permiso."""

        # Validación de unicidad
        if Permission.query.filter_by(name=permission_data.name).first():
            abort(409, message="Ese permiso ya existe.")

        db.session.add(permission_data)
        db.session.commit()
        return permission_data


# ---------------------------------------------------------
# GET / PUT / DELETE POR ID
# ---------------------------------------------------------
@blp.route("/permissions/<int:id>")
class PermissionById(MethodView):

    @blp.response(200, PermissionSchema)
    def get(self, id):
        permission = Permission.query.get_or_404(id)
        return permission

    @blp.arguments(PermissionSchema)
    @blp.response(200, PermissionSchema)
    def put(self, update_data, id):
        permission = Permission.query.get_or_404(id)

        # Validación: si cambia el nombre, evitar duplicados
        if update_data.name != permission.name:
            if Permission.query.filter_by(name=update_data.name).first():
                abort(409, message="Ya existe un permiso con ese nombre.")

        permission.name = update_data.name
        permission.description = update_data.description

        db.session.commit()
        return permission

    @blp.response(200)
    def delete(self, id):
        permission = Permission.query.get_or_404(id)

        # Evitar borrar permisos que están en uso (opcional pero recomendado)
        if permission.roles:
            abort(400, message="No se puede eliminar porque está asociado a uno o más roles.")

        db.session.delete(permission)
        db.session.commit()

        return {"message": "Permiso eliminado correctamente."}


# ---------------------------------------------------------
# ASIGNAR PERMISO A ROL
# ---------------------------------------------------------
@blp.route("/permissions/<int:perm_id>/assign-role/<int:role_id>", methods=["POST"])
class AssignPermissionToRole(MethodView):

    def post(self, perm_id, role_id):
        permission = Permission.query.get_or_404(perm_id)
        role = Role.query.get_or_404(role_id)

        if permission in role.permissions:
            abort(400, message="Ese rol ya tiene este permiso asignado.")

        role.permissions.append(permission)
        db.session.commit()

        return {
            "message": f"Permiso '{permission.name}' asignado al rol '{role.name}'."
        }


# ---------------------------------------------------------
# REMOVER PERMISO DE ROL
# ---------------------------------------------------------
@blp.route("/permissions/<int:perm_id>/remove-role/<int:role_id>", methods=["DELETE"])
class RemovePermissionFromRole(MethodView):

    def delete(self, perm_id, role_id):
        permission = Permission.query.get_or_404(perm_id)
        role = Role.query.get_or_404(role_id)

        if permission not in role.permissions:
            abort(404, message="Ese rol no tiene este permiso asignado.")

        role.permissions.remove(permission)
        db.session.commit()

        return {
            "message": f"Permiso '{permission.name}' removido del rol '{role.name}'."
        }
