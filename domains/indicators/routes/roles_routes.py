from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required

from domains.indicators.handlers.role_handler import RoleHandler
from domains.indicators.schemas.role_schema import RoleSchema

blp = Blueprint(
    "roles",
    "roles",
    url_prefix="/roles",
    description="Roles"
)


@blp.route("/")
class RoleListResource(MethodView):

    @jwt_required()
    @blp.response(200, RoleSchema(many=True))
    def get(self):
        return RoleHandler.get_all()


@blp.route("/<int:role_id>")
class RoleResource(MethodView):

    @jwt_required()
    @blp.response(200, RoleSchema)
    def get(self, role_id):
        role = RoleHandler.get_by_id(role_id)
        if not role:
            return {"message": "Role not found"}, 404
        return role
