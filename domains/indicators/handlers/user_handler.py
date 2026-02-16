from extensions import db

from domains.indicators.models.User.user import User
from domains.indicators.validators.user_validator import UserValidator


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
            profile_image_url=data.get('profile_image_url')
        )

        user.set_password(data['password'])

        db.session.add(user)
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
        for field in ['first_name', 'last_name', 'email', 'profile_image_url']:
            if field in data:
                setattr(user, field, data[field])

        if 'password' in data:
            user.set_password(data['password'])

        db.session.commit()
        return user

    @staticmethod
    def delete(user):
        user.is_active = False
        db.session.commit()
