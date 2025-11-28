from flask_smorest import Blueprint
from flask.views import MethodView
from extensions import db
from models.role import Role
from schemas.role_schema import RoleSchema
from validators.role_validator import RoleValidator

blp = Blueprint("Roles", "roles", description="Gestión de roles")


@blp.route("/roles")
class RoleList(MethodView):

    @blp.response(200, RoleSchema(many=True))
    def get(self):
        return Role.query.all()

    @blp.arguments(RoleSchema)
    @blp.response(201, RoleSchema)
    def post(self, data):

        RoleValidator.name_unique(data["name"])

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

        if data["name"] != role.name:
            RoleValidator.name_unique(data["name"], id)

        role.name = data["name"]
        role.description = data.get("description")

        db.session.commit()
        return role

    def delete(self, id):
        role = Role.query.get_or_404(id)

        RoleValidator.can_delete(role)

        db.session.delete(role)
        db.session.commit()

        return {"message": "Rol eliminado correctamente."}
