from flask_smorest import abort
from models.user import User
from models.role import Role


class UserValidator:

    @staticmethod
    def email_unique(email, user_id=None):
        """Valida que no exista otro usuario con ese email."""
        query = User.query.filter_by(email=email)

        if user_id:
            query = query.filter(User.id != user_id)

        if query.first():
            abort(409, message="Este email ya está registrado por otro usuario.")

    @staticmethod
    def role_exists(role_id):
        """Valida que el rol exista."""
        role = Role.query.get(role_id)
        if not role:
            abort(400, message="El rol seleccionado no existe.")
        return role

    @staticmethod
    def cannot_delete_last_admin(user):
        """Evita borrar el último administrador."""
        if user.role and user.role.name.lower() == "admin":
            admins = User.query.join(Role).filter(Role.name=="admin").count()
            if admins <= 1:
                abort(400, message="No se puede eliminar el único administrador del sistema.")
