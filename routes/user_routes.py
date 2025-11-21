from flask_smorest import Blueprint, abort
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from extensions import db

from models.user import User
from models.role import Role
from schemas.user_schema import UserSchema

blp = Blueprint("Users", "users", description="Gestión de usuarios")

# -------------------------------------------------------
# LISTAR + CREAR
# -------------------------------------------------------
@blp.route("/users")
class UsersList(MethodView):

    @jwt_required()
    @blp.response(200, UserSchema(many=True))
    def get(self):
        """Listar todos los usuarios con su rol"""
        return User.query.all()

    @jwt_required()
    @blp.arguments(UserSchema)
    @blp.response(201, UserSchema)
    def post(self, data):
        """Crear usuario (1 solo rol)"""

        # Validar email único
        if User.query.filter_by(email=data.get("email")).first():
            abort(409, message="Este email ya está registrado.")

        # Crear usuario
        user = User(
            name=data.get("name"),
            email=data.get("email")
        )

        # Setear contraseña
        if not data.get("password"):
            abort(400, message="La contraseña es obligatoria.")
        user.set_password(data["password"])

        # Asignar rol
        role_id = data.get("role_id")
        role = Role.query.get(role_id)
        if not role:
            abort(400, message="El rol seleccionado no existe.")

        user.roles = [role]

        db.session.add(user)
        db.session.commit()

        return user


# -------------------------------------------------------
# GET ONE + UPDATE + DELETE
# -------------------------------------------------------
@blp.route("/users/<int:user_id>")
class UserById(MethodView):

    @jwt_required()
    @blp.response(200, UserSchema)
    def get(self, user_id):
        user = User.query.get(user_id)
        if not user:
            abort(404, message="Usuario no encontrado.")
        return user

    @jwt_required()
    @blp.arguments(UserSchema)
    @blp.response(200, UserSchema)
    def put(self, data, user_id):
        user = User.query.get(user_id)
        if not user:
            abort(404, message="Usuario no encontrado.")

        # Actualizar campos simples
        if "name" in data:
            user.name = data["name"]

        if "email" in data:
            user.email = data["email"]

        # Actualizar contraseña si viene
        if "password" in data and data["password"]:
            user.set_password(data["password"])

        # Actualizar rol si viene
        if "role_id" in data:
            role = Role.query.get(data["role_id"])
            if not role:
                abort(400, message="El rol seleccionado no existe.")
            user.roles = [role]

        db.session.commit()
        return user

    @jwt_required()
    def delete(self, user_id):
        user = User.query.get(user_id)
        if not user:
            abort(404, message="Usuario no encontrado.")

        db.session.delete(user)
        db.session.commit()

        return {"message": "Usuario eliminado correctamente."}
