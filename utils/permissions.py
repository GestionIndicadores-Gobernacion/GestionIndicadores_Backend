from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from models.user import User

def permission_required(permission_name):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()  # asegura JWT válido
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            if not user or not user.active:
                abort(401, message="Usuario inválido o inactivo.")

            # recolectar permisos desde roles
            user_permissions = {p.name for role in user.roles for p in role.permissions}
            if permission_name not in user_permissions:
                abort(403, message="No tienes permiso para esta acción.")
            return fn(*args, **kwargs)
        return wrapper
    return decorator
