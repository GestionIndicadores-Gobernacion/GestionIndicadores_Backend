from domains.indicators.models.Role.role import Role


class RoleHandler:

    @staticmethod
    def get_all():
        return Role.query.order_by(Role.id.asc()).all()

    @staticmethod
    def get_by_id(role_id):
        return Role.query.get(role_id)
