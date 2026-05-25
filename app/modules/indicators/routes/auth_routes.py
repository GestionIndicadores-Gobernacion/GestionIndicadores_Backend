from datetime import datetime, timezone

from flask import jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    get_jwt,
    create_access_token,
    create_refresh_token,
)

from app.core.extensions import limiter
from app.modules.indicators.services.auth_handler import AuthHandler
from app.modules.indicators.services.token_blocklist import revoke_jti
from app.shared.models.user import User
from app.shared.schemas.auth_schema import LoginSchema
from app.shared.schemas.user_schema import UserSchema


def _exp_to_datetime(payload: dict) -> datetime | None:
    """Convierte el claim `exp` (epoch UTC) a datetime tz-aware."""
    exp = payload.get("exp")
    if not exp:
        return None
    return datetime.fromtimestamp(int(exp), tz=timezone.utc)

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
        """
        Rota access + refresh.

        * Valida que el usuario exista y esté activo.
        * Emite un nuevo access token con los claims `role_id` / `role`
          (mismo contrato que /login) — sin esto el frontend pierde el
          rol tras el primer refresh.
        * Emite un nuevo refresh token y revoca el jti del anterior.
        * El callback `token_in_blocklist_loader` ya valida que el
          refresh entrante no esté revocado; si lo está, esta función
          ni siquiera se ejecuta (responde 401 token_revoked).

        Respuesta siempre incluye `access_token` y `refresh_token` —
        el frontend antiguo que solo lee `access_token` sigue siendo
        compatible.
        """
        payload = get_jwt()
        user_id_str = str(get_jwt_identity())

        # Refresh emite también el claim `permissions` para mantener el
        # contrato del Bloque 6. Eager-load del rol y permisos en a lo sumo
        # 3 SELECTs (mismo helper que login).
        from app.modules.indicators.services.auth_handler import _eager_user_query
        from app.utils.permissions import get_effective_permissions

        user = _eager_user_query().filter(User.id == int(user_id_str)).first()
        if not user:
            return {"msg": "Usuario no encontrado.", "error": "user_not_found"}, 401
        if not user.is_active:
            return {"msg": "Usuario inactivo.", "error": "user_inactive"}, 401

        # Revocar el refresh entrante ANTES de emitir el nuevo. Si por
        # cualquier razón fallara la emisión, la fila queda en BD y el
        # usuario será forzado a re-loguear (fail-safe).
        old_jti = payload.get("jti")
        if old_jti:
            revoke_jti(
                old_jti,
                token_type="refresh",
                expires_at=_exp_to_datetime(payload),
            )

        extra_claims = {
            "role_id": user.role_id,
            "role": user.role.name if user.role else None,
            "permissions": sorted(get_effective_permissions(user)),
        }
        access_token = create_access_token(
            identity=user_id_str,
            additional_claims=extra_claims,
        )
        refresh_token = create_refresh_token(identity=user_id_str)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }



@blp.route("/logout")
class LogoutResource(MethodView):

    @jwt_required()
    def post(self):
        # Revoca el jti del access token. El frontend también debe borrar
        # localStorage, pero si alguien robó el token, a partir de ahora
        # el backend lo rechazará.
        payload = get_jwt()
        jti = payload.get("jti")
        if jti:
            revoke_jti(jti, token_type="access", expires_at=_exp_to_datetime(payload))
        return {"message": "Logged out successfully"}, 200


@blp.route("/logout-refresh")
class LogoutRefreshResource(MethodView):
    """Revoca el refresh token (endpoint opcional pero recomendado en logout)."""

    @jwt_required(refresh=True)
    def post(self):
        payload = get_jwt()
        jti = payload.get("jti")
        if jti:
            revoke_jti(jti, token_type="refresh", expires_at=_exp_to_datetime(payload))
        return {"message": "Refresh revoked"}, 200
