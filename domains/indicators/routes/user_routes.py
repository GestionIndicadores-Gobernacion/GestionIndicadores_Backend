from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required

from domains.indicators.handlers.user_handler import UserHandler
from domains.indicators.schemas.user_schema import UserSchema
from utils.permissions import role_required

blp = Blueprint(
    "users",
    "users",
    url_prefix="/users",
    description="User management"
)


# ── CRUD base ────────────────────────────────────────────────────────────────

@blp.route("/")
class UserListResource(MethodView):

    @jwt_required()
    @blp.response(200, UserSchema(many=True))
    def get(self):
        return UserHandler.get_all()

    @jwt_required()
    @role_required("admin")
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
        user = UserHandler.get_by_id(user_id)
        if not user:
            return {"message": "User not found"}, 404
        return user

    @jwt_required()
    @role_required("admin")
    @blp.arguments(UserSchema(partial=True))
    @blp.response(200, UserSchema)
    def put(self, data, user_id):
        """Editar usuario. Si incluye component_ids, reemplaza todas las asignaciones."""
        user = UserHandler.get_by_id(user_id)
        if not user:
            return {"message": "User not found"}, 404
        return UserHandler.update(user, data)

    @jwt_required()
    @role_required("admin")
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
    @role_required("admin")
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
    @role_required("admin")
    @blp.response(204)
    def delete(self, user_id, component_id):
        """Quitar un componente de un usuario."""
        removed = UserHandler.remove_component(user_id, component_id)
        if not removed:
            return {"message": "Assignment not found"}, 404