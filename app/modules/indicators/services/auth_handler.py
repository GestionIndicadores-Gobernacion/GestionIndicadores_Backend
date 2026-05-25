from flask_jwt_extended import (
    create_access_token,
    create_refresh_token
)
from sqlalchemy.orm import joinedload, selectinload

from app.shared.models.user import User
from app.shared.models.role import Role
from app.shared.models.role_permission import RolePermission
from app.shared.models.user_permission import UserPermission
from app.shared.schemas.user_schema import UserSchema
from app.utils.permissions import get_effective_permissions


def _eager_user_query():
    """Query base con eager-load de rol + permisos.

    Pre-carga en a lo sumo 3 SELECTs para que `get_effective_permissions`
    no dispare N+1 al computar el set. Lo usan login y refresh.
    """
    return User.query.options(
        joinedload(User.role)
          .selectinload(Role.role_permissions)
          .joinedload(RolePermission.permission),
        selectinload(User.permission_overrides)
          .joinedload(UserPermission.permission),
    )


class AuthHandler:

    @staticmethod
    def login(data):
        user = _eager_user_query().filter_by(email=data['email']).first()

        if not user or not user.check_password(data['password']):
            return None, 'Invalid credentials'

        if not user.is_active:
            return None, 'User is inactive'

        # Una sola computación de permisos para esta request: el set se
        # usa tanto en el JWT como en el dump del UserSchema. El cache de
        # `g` evita recálculo si algún middleware lo consultara después.
        perms = sorted(get_effective_permissions(user))

        access_token = create_access_token(
            identity=str(user.id),
            additional_claims={
                "role_id": user.role_id,
                "role": user.role.name,
                "permissions": perms,
            },
        )
        refresh_token = create_refresh_token(identity=str(user.id))

        # Pasamos los permisos por contexto al schema; ver UserSchema.get_permissions
        # — es la única forma en login porque aún no hay JWT en flight.
        user_schema = UserSchema()
        user_schema.context["precomputed_permissions"] = perms
        user_schema.context["precomputed_permissions_for_user_id"] = user.id

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": user_schema.dump(user),
        }, None

