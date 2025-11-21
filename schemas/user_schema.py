from marshmallow import fields, validates, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from extensions import db
from models.user import User
import re
from schemas.role_schema import RoleSchema


class UserSchema(SQLAlchemyAutoSchema):

    # ---- CAMPOS QUE SE PUEDEN RECIBIR ----
    password = fields.String(load_only=True)   # opcional en update
    name = fields.String(required=False)
    email = fields.String(required=False)

    # ---- ROLE ----
    # Lista de roles (normalmente solo 1)
    roles = fields.Nested(RoleSchema, many=True, dump_only=True)

    # role_id SE PUEDE ENVIAR Y TAMBIÉN SE PUEDE MOSTRAR
    role_id = fields.Integer(required=False)

    class Meta:
        model = User
        load_instance = True
        sqla_session = db.session
        include_fk = True
        exclude = ("password_hash",)

    # ---------------------------------------
    #   VALIDACIONES
    # ---------------------------------------

    @validates("name")
    def validate_name(self, value):
        if value and len(value) < 3:
            raise ValidationError("El nombre debe tener mínimo 3 caracteres.")
        if value and not re.match(r"^[a-zA-ZÀ-ÿ\s]+$", value):
            raise ValidationError("El nombre solo puede contener letras.")

    @validates("email")
    def validate_email(self, value):
        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if value and not re.match(email_regex, value):
            raise ValidationError("Formato de email inválido.")

    @validates("password")
    def validate_password(self, value):
        if value and len(value) < 6:
            raise ValidationError("La contraseña debe tener mínimo 6 caracteres.")
