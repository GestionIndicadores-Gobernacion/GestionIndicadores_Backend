from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token, 
    jwt_required, 
    get_jwt_identity
)

from models.user import User
from schemas.user_schema import UserSchema
from schemas.login_schema import LoginSchema
from schemas.register_schema import RegisterSchema
from extensions import db
from models.role import Role

blp = Blueprint("Auth", "auth", description="Autenticación y usuarios")

# ---------------------------------------------------
# REGISTER
# ---------------------------------------------------
@blp.route("/auth/register")
class Register(MethodView):

    @blp.arguments(RegisterSchema)
    @blp.response(201, UserSchema)
    def post(self, user_data):

        # 1. Validar email duplicado
        if User.query.filter_by(email=user_data["email"]).first():
            abort(409, message="Este correo ya está registrado.")

        # 2. Crear usuario
        user = User(
            name=user_data["name"],
            email=user_data["email"],
        )
        user.set_password(user_data["password"])

        # 3. Buscar el rol Viewer
        viewer_role = Role.query.filter_by(name="Viewer").first()
        if not viewer_role:
            abort(500, message="El rol VIEWER no existe. Ejecuta el seed.")

        # 4. Asignar el rol Viewer
        user.roles.append(viewer_role)

        # 5. Guardar en BD
        db.session.add(user)
        db.session.commit()

        return user
# ---------------------------------------------------
# LOGIN
# ---------------------------------------------------
@blp.route("/auth/login")
class Login(MethodView):

    @blp.arguments(LoginSchema)
    def post(self, login_data):

        user = User.query.filter_by(email=login_data["email"]).first()

        if not user or not user.check_password(login_data["password"]):
            abort(401, message="❌ Credenciales inválidas")

        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

        return {
            "message": "✔ Login exitoso",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": UserSchema(exclude=["password"]).dump(user)
        }


# ---------------------------------------------------
# REFRESH TOKEN
# ---------------------------------------------------
@blp.route("/auth/refresh")
class Refresh(MethodView):

    @jwt_required(refresh=True)
    def post(self):
        user_id = get_jwt_identity()  # string
        new_token = create_access_token(identity=user_id)
        return {"access_token": new_token}


# ---------------------------------------------------
# PROFILE
# ---------------------------------------------------
@blp.route("/auth/me")
class Profile(MethodView):

    @jwt_required()
    @blp.response(200, UserSchema)
    def get(self):
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)

        if not user:
            abort(404, message="Usuario no encontrado.")

        return user
