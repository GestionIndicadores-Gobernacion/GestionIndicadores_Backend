from flask_smorest import abort
from models.role import Role


class RoleValidator:

    @staticmethod
    def name_unique(name, role_id=None):
        query = Role.query.filter_by(name=name)

        if role_id:
            query = query.filter(Role.id != role_id)

        if query.first():
            abort(409, message="Ya existe un rol con ese nombre.")

    @staticmethod
    def can_delete(role):
        if role.users:
            abort(400, message="No se puede eliminar un rol que tiene usuarios asignados.")
