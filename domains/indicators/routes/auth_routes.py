from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    create_access_token
)

from domains.indicators.handlers.auth_handler import AuthHandler
from domains.indicators.schemas.auth_schema import LoginSchema
from domains.indicators.schemas.user_schema import UserSchema

blp = Blueprint(
    "auth",
    "auth",
    url_prefix="/auth",
    description="Authentication"
)


@blp.route("/login")
class LoginResource(MethodView):

    @blp.arguments(LoginSchema)
    def post(self, data):
        result, error = AuthHandler.login(data)
        if error:
            return {"message": error}, 401

        return {
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "user": UserSchema().dump(result["user"])
        }


@blp.route("/refresh")
class RefreshResource(MethodView):

    @jwt_required(refresh=True)
    def post(self):
        user_id = str(get_jwt_identity())  # ✅ fuerza string
        access_token = create_access_token(identity=user_id)
        return {"access_token": access_token}



@blp.route("/logout")
class LogoutResource(MethodView):

    @jwt_required()
    def post(self):
        # Stateless JWT → el frontend elimina tokens
        return {"message": "Logged out successfully"}, 200
