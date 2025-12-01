from flask_smorest import Blueprint, abort
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from extensions import db

from models.user import User
from schemas.user_schema import UserSchema, UserUpdateSchema
from validators.user_validator import UserValidator

blp = Blueprint("Users", "users", description="Gestión de usuarios")


@blp.route("/users")
class UsersList(MethodView):

    @blp.response(200, UserSchema(many=True))
    def get(self):
        return User.query.all()

    @blp.arguments(UserSchema)
    @blp.response(201, UserSchema)
    def post(self, data):

        # Validación: email único
        UserValidator.email_unique(data["email"])

        # Validación: rol existe
        role = UserValidator.role_exists(data["role_id"])

        user = User(
            name=data["name"],
            email=data["email"]
        )
        user.set_password(data["password"])
        user.role = role

        db.session.add(user)
        db.session.commit()

        return user


@blp.route("/users/<int:user_id>")
class UserById(MethodView):

    @blp.response(200, UserSchema)
    def get(self, user_id):
        return User.query.get_or_404(user_id)

    @blp.arguments(UserUpdateSchema)
    @blp.response(200, UserSchema)
    def put(self, data, user_id):

        user = User.query.get_or_404(user_id)

        # Validar email único
        if "email" in data:
            UserValidator.email_unique(data["email"], user.id)
            user.email = data["email"]

        if "name" in data:
            user.name = data["name"]

        if "password" in data and data["password"]:
            user.set_password(data["password"])

        if "role_id" in data:
            user.role = UserValidator.role_exists(data["role_id"])

        db.session.commit()
        return user

    @jwt_required()
    def delete(self, user_id):
        user = User.query.get_or_404(user_id)

        # No permitir eliminar último administrador
        UserValidator.cannot_delete_last_admin(user)

        db.session.delete(user)
        db.session.commit()

        return {"message": "Usuario eliminado correctamente."}
