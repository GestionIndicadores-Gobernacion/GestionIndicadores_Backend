from flask_smorest import Blueprint, abort
from flask.views import MethodView
from extensions import db
from models.role import Role
from models.permission import Permission
from schemas.role_schema import RoleSchema

blp = Blueprint("Roles", "roles", description="Gestión de roles")

@blp.route("/roles")
class RoleList(MethodView):

    @blp.response(200, RoleSchema(many=True))
    def get(self):
        return Role.query.all()

    @blp.arguments(RoleSchema)
    @blp.response(201, RoleSchema)
    def post(self, data):

        # Validación nombre único
        if Role.query.filter_by(name=data["name"]).first():
            abort(409, message="Ya existe un rol con ese nombre.")

        role = Role(
            name=data["name"],
            description=data.get("description")
        )

        db.session.add(role)
        db.session.flush()

        # Asignar permisos manualmente
        perm_ids = data.get("permissions", [])
        if perm_ids:
            perms = Permission.query.filter(Permission.id.in_(perm_ids)).all()
            role.permissions = perms

        db.session.commit()
        return role

@blp.route("/roles/<int:id>")
class RoleById(MethodView):

    @blp.response(200, RoleSchema)
    def get(self, id):
        return Role.query.get_or_404(id)
    
    @blp.arguments(RoleSchema)
    @blp.response(200, RoleSchema)
    def put(self, data, id):
        role = Role.query.get_or_404(id)

        if data["name"] != role.name:
            if Role.query.filter_by(name=data["name"]).first():
                abort(409, message="Ya existe un rol con ese nombre.")

        role.name = data["name"]
        role.description = data.get("description")

        # Actualizar permisos
        if "permissions" in data:
            perm_ids = data["permissions"] or []
            perms = Permission.query.filter(Permission.id.in_(perm_ids)).all()
            role.permissions = perms

        db.session.commit()
        return role


    def delete(self, id):
        role = Role.query.get_or_404(id)

        if role.users:
            abort(400, message="No se puede eliminar un rol que tiene usuarios asignados.")

        db.session.delete(role)
        db.session.commit()

        return {"message": "Rol eliminado correctamente."}

@blp.route("/roles/<int:role_id>/assign-permission/<int:perm_id>", methods=["POST"])
class AssignPermissionToRole(MethodView):
    def post(self, role_id, perm_id):
        role = Role.query.get_or_404(role_id)
        perm = Permission.query.get_or_404(perm_id)

        if perm in role.permissions:
            abort(400, message="El rol ya tiene este permiso.")

        role.permissions.append(perm)
        db.session.commit()

        return {"message": "Permiso asignado correctamente."}
    
@blp.route("/roles/<int:role_id>/remove-permission/<int:perm_id>", methods=["DELETE"])
class RemovePermissionFromRole(MethodView):
    def delete(self, role_id, perm_id):
        role = Role.query.get_or_404(role_id)
        perm = Permission.query.get_or_404(perm_id)

        if perm not in role.permissions:
            abort(404, message="El rol no tiene este permiso.")

        role.permissions.remove(perm)
        db.session.commit()

        return {"message": "Permiso removido correctamente."}

