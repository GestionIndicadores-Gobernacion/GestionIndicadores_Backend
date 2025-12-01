from marshmallow import Schema, fields, validates, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from extensions import db
from models.user import User
import re
from schemas.role_schema import RoleSchema


# =====================================================================
#  ESQUEMA PRINCIPAL (CREATE / READ)
# =====================================================================
class UserSchema(SQLAlchemyAutoSchema):

    password = fields.String(load_only=True)
    name = fields.String(required=False)
    email = fields.String(required=False)

    # Rol asociado (dump)
    role = fields.Nested(RoleSchema, dump_only=True)

    # Permite enviar role_id
    role_id = fields.Integer(required=False)

    class Meta:
        model = User
        load_instance = False
        sqla_session = db.session
        include_fk = True
        exclude = ("password_hash",)

    # -------- Validaciones --------

    @validates("name")
    def validate_name(self, value, **kwargs):
        if value and len(value) < 3:
            raise ValidationError("El nombre debe tener mínimo 3 caracteres.")
        if value and not re.match(r"^[a-zA-ZÀ-ÿ\s]+$", value):
            raise ValidationError("El nombre solo puede contener letras.")
        
    @validates("email")
    def validate_email(self, value, **kwargs):
        email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if value and not re.match(email_regex, value):
            raise ValidationError("Formato de email inválido.")

    @validates("password")
    def validate_password(self, value, **kwargs):
        if value and len(value) < 6:
            raise ValidationError("La contraseña debe tener mínimo 6 caracteres.")

# =====================================================================
#  ESQUEMA PARA UPDATE (SOLO DICT)
# =====================================================================
class UserUpdateSchema(Schema):
    name = fields.String(required=False)
    email = fields.String(required=False)
    password = fields.String(required=False)
    role_id = fields.Integer(required=False)
