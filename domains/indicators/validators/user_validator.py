from domains.indicators.models.User.user import User


class UserValidator:

    @staticmethod
    def validate_create(data):
        errors = {}

        if not data.get('first_name', '').strip():
            errors['first_name'] = 'first_name is required'

        if not data.get('last_name', '').strip():
            errors['last_name'] = 'last_name is required'

        if not data.get('email', '').strip():
            errors['email'] = 'email is required'

        if not data.get('password'):
            errors['password'] = 'password is required'

        # Email unique
        if data.get('email'):
            if User.query.filter_by(email=data['email']).first():
                errors['email'] = 'Email already exists'

        return errors
