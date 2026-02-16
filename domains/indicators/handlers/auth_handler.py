from flask_jwt_extended import (
    create_access_token,
    create_refresh_token
)
from domains.indicators.models.User.user import User
from domains.indicators.schemas.user_schema import UserSchema


class AuthHandler:

    @staticmethod
    def login(data):
        user = User.query.filter_by(email=data['email']).first()

        if not user or not user.check_password(data['password']):
            return None, 'Invalid credentials'

        if not user.is_active:
            return None, 'User is inactive'

        # 🔥 fuerza la carga del rol (seguro con lazy)
        _ = user.role

        user_schema = UserSchema()  # 👈 INSTANCIA

        return {
    "access_token": create_access_token(
        identity=str(user.id),   # ✅ STRING
        additional_claims={
            "role_id": user.role_id,
            "role": user.role.name
        }
    ),
    "refresh_token": create_refresh_token(
        identity=str(user.id)    # ✅ STRING
    ),
    "user": user_schema.dump(user)
}, None

