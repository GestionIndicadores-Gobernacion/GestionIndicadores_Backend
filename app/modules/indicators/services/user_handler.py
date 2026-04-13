from app.core.extensions import db

from app.shared.models.user import User
from app.shared.models.user_component import UserComponent
from app.modules.indicators.validators.user_validator import UserValidator


class UserHandler:

    @staticmethod
    def create(data):
        errors = UserValidator.validate_create(data)
        if errors:
            return None, errors

        user = User(
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data['email'],
            profile_image_url=data.get('profile_image_url'),
            role_id=data.get('role_id', 1)
        )
        user.set_password(data['password'])
        db.session.add(user)
        db.session.flush()  # obtiene user.id antes del commit

        # Asignar componentes si vienen en el payload
        component_ids = data.get('component_ids', [])
        for cid in component_ids:
            db.session.add(UserComponent(user_id=user.id, component_id=cid))

        db.session.commit()
        return user, None

    @staticmethod
    def get_all():
        return User.query.order_by(User.created_at.desc()).all()

    @staticmethod
    def get_by_id(user_id):
        return User.query.get(user_id)

    @staticmethod
    def update(user, data):
        for field in ['first_name', 'last_name', 'email', 'profile_image_url', 'role_id']:
            if field in data:
                setattr(user, field, data[field])

        if 'password' in data:
            user.set_password(data['password'])

        # Reemplazar asignaciones de componentes si se envían
        if 'component_ids' in data:
            UserComponent.query.filter_by(user_id=user.id).delete()
            for cid in data['component_ids']:
                db.session.add(UserComponent(user_id=user.id, component_id=cid))

        db.session.commit()
        return user

    @staticmethod
    def delete(user):
        user.is_active = False
        db.session.commit()

    # ── Asignaciones individuales ────────────────────────────────────────

    @staticmethod
    def assign_component(user_id, component_id):
        """Asigna un componente a un usuario. Ignora si ya existe."""
        exists = UserComponent.query.filter_by(
            user_id=user_id, component_id=component_id
        ).first()
        if exists:
            return exists, None

        uc = UserComponent(user_id=user_id, component_id=component_id)
        db.session.add(uc)
        db.session.commit()
        return uc, None

    @staticmethod
    def remove_component(user_id, component_id):
        """Quita la asignación de un componente a un usuario."""
        uc = UserComponent.query.filter_by(
            user_id=user_id, component_id=component_id
        ).first()
        if not uc:
            return False
        db.session.delete(uc)
        db.session.commit()
        return True