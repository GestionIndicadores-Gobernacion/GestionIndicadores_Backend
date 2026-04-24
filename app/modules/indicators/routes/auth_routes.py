from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    get_jwt,
    create_access_token,
)

from app.core.extensions import limiter
from app.modules.indicators.services.auth_handler import AuthHandler
from app.modules.indicators.services.token_blocklist import revoke_jti
from app.shared.schemas.auth_schema import LoginSchema
from app.shared.schemas.user_schema import UserSchema

blp = Blueprint(
    "auth",
    "auth",
    url_prefix="/auth",
    description="Authentication"
)


@blp.route("/login")
class LoginResource(MethodView):

    # Límite por IP: protege contra fuerza bruta sin molestar a usuarios
    # legítimos. Supera ~8 intentos/min → 429.
    decorators = [limiter.limit("8 per minute; 30 per hour")]

    @blp.arguments(LoginSchema)
    def post(self, data):
        result, error = AuthHandler.login(data)
        if error:
            return {"message": error}, 401

        return {
            "access_token": result["access_token"],
            "refresh_token": result["refresh_token"],
            "user": result["user"]
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
        # Revoca el jti del access token. El frontend también debe borrar
        # localStorage, pero si alguien robó el token, a partir de ahora
        # el backend lo rechazará.
        jti = get_jwt().get("jti")
        if jti:
            revoke_jti(jti)
        return {"message": "Logged out successfully"}, 200


@blp.route("/logout-refresh")
class LogoutRefreshResource(MethodView):
    """Revoca el refresh token (endpoint opcional)."""

    @jwt_required(refresh=True)
    def post(self):
        jti = get_jwt().get("jti")
        if jti:
            revoke_jti(jti)
        return {"message": "Refresh revoked"}, 200
