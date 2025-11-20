from flask import request
from flask_smorest import Blueprint, abort
from flask.views import MethodView
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from db import db
from models.user import User
from schemas.user_schema import UserSchema
from utils.security import hash_password, verify_password

blp = Blueprint("Auth", "auth", description="Autenticación")

@blp.route("/auth/register")
class Register(MethodView):

    @blp.arguments(UserSchema)
    @blp.response(201, UserSchema)
    def post(self, new_user):
        # espera username, email y password en payload (password no es parte del schema -> manejar aquí)
        raw_password = request.json.get("password")
        if not raw_password:
            abort(400, message="Password requerido.")

        # validar unicidad
        if User.query.filter((User.username == new_user.username) | (User.email == new_user.email)).first():
            abort(400, message="Usuario o email ya registrado.")

        new_user.password_hash = hash_password(raw_password)
        db.session.add(new_user)
        db.session.commit()
        return new_user


@blp.route("/auth/login")
class Login(MethodView):

    @blp.arguments(UserSchema, location="json")
    def post(self, data):
        # espera { "username": "...", "password": "..." } o email en username
        username = data.get("username")
        raw_password = request.json.get("password")
        if not username or not raw_password:
            abort(400, message="username y password requeridos.")

        user = User.query.filter((User.username == username) | (User.email == username)).first()
        if not user or not verify_password(raw_password, user.password_hash):
            abort(401, message="Credenciales inválidas.")

        access = create_access_token(identity=user.id)
        refresh = create_refresh_token(identity=user.id)
        return {"access_token": access, "refresh_token": refresh}

@blp.route("/auth/refresh")
class RefreshToken(MethodView):
    @jwt_required(refresh=True)
    def post(self):
        current_user = get_jwt_identity()
        new_access = create_access_token(identity=current_user)
        return {"access_token": new_access}
