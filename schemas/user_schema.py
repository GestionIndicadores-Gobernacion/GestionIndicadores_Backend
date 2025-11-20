from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import fields
from models.user import User

class UserSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        include_relationships = True
        # ⛔ No incluir hash de contraseña ni relaciones secundarias innecesarias
        exclude = ("password_hash",)
    
    # Si quieres permitir enviar contraseña en solicitudes de registro:
    password = fields.String(load_only=True, required=True)
