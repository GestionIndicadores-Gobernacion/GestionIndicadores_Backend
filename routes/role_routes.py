from flask_smorest import Blueprint, abort
from flask.views import MethodView
from db import db
from models.role import Role
from schemas.role_schema import RoleSchema
from models.permission import Permission

blp = Blueprint("Roles", "roles", description="Gestión de roles")

@blp.route("/roles")
class RoleList(MethodView):

    @blp.response(200, RoleSchema(many=True))
    def get(self):
        return Role.query.all()

    @blp.arguments(RoleSchema)
    @blp.response(201, RoleSchema)
    def post(self, role_data):
        # role_data puede contener permissions con ids o names (ajusta según preferencia)
        db.session.add(role_data)
        db.session.commit()
        return role_data

@blp.route("/roles/<int:id>/assign-permission/<int:perm_id>", methods=["POST"])
class RoleAssignPerm(MethodView):
    def post(self, id, perm_id):
        role = Role.query.get_or_404(id)
        perm = Permission.query.get_or_404(perm_id)
        if perm not in role.permissions:
            role.permissions.append(perm)
            db.session.commit()
        return {"message": "Permiso asignado"}
