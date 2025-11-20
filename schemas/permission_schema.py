from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import validates, ValidationError, fields
from models.permission import Permission
from extensions import db

class PermissionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Permission
        load_instance = True
        sqla_session = db.session
        include_fk = True

    name = fields.String(required=True)
    description = fields.String(allow_none=True)

    @validates("name")
    def validate_name(self, value):
        if not value.strip():
            raise ValidationError("El nombre del permiso es obligatorio.")
        if len(value) < 3:
            raise ValidationError("Debe tener al menos 3 caracteres.")
        if len(value) > 120:
            raise ValidationError("Máximo 120 caracteres permitidos.")
