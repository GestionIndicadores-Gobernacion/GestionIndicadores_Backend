from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from domains.indicators.handlers.user_handler import UserHandler
from domains.indicators.schemas.user_schema import UserSchema
from utils.permissions import role_required

blp = Blueprint(
    "users",
    "users",
    url_prefix="/users",
    description="User management"
)

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
    @blp.arguments(UserSchema(partial=True))
    @blp.response(200, UserSchema)
    def put(self, data, user_id):
        user = UserHandler.get_by_id(user_id)
        if not user:
            return {"message": "User not found"}, 404
        return UserHandler.update(user, data)

    @jwt_required()
    @blp.response(204)
    def delete(self, user_id):
        user = UserHandler.get_by_id(user_id)
        if not user:
            return {"message": "User not found"}, 404
        UserHandler.delete(user)


@blp.route("/me")
class UserMeResource(MethodView):

    @jwt_required()
    @blp.response(200, UserSchema)
    def get(self):
        user_id = get_jwt_identity()
        user = UserHandler.get_by_id(user_id)

        if not user:
            return {"message": "User not found"}, 404

        return user
