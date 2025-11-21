from flask_smorest import Blueprint, abort
from flask.views import MethodView
from extensions import db
from models.role import Role
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

        # Validar nombre único
        if data["name"] != role.name:
            if Role.query.filter_by(name=data["name"]).first():
                abort(409, message="Ya existe un rol con ese nombre.")

        role.name = data["name"]
        role.description = data.get("description")

        db.session.commit()
        return role

    def delete(self, id):
        role = Role.query.get_or_404(id)

        # Evitar borrar un rol en uso
        if role.users:
            abort(400, message="No se puede eliminar un rol que tiene usuarios asignados.")

        db.session.delete(role)
        db.session.commit()

        return {"message": "Rol eliminado correctamente."}
