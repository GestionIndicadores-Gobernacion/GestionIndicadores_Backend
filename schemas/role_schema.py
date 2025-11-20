from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import fields, validates, ValidationError
from extensions import db
from models.role import Role
from models.permission import Permission

class RoleSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Role
        load_instance = False  # 🔥 IMPORTANTE
        sqla_session = db.session
        include_fk = True

    name = fields.String(required=True)
    description = fields.String(allow_none=True)
    permissions = fields.List(fields.Integer(), required=False, load_only=True)
    
    @validates("name")
    def validate_name(self, value, **kwargs):
        if not value.strip():
            raise ValidationError("El nombre del rol es obligatorio.")
        if len(value) < 3:
            raise ValidationError("Debe tener al menos 3 caracteres.")
        if len(value) > 120:
            raise ValidationError("Máximo 120 caracteres permitidos.")

    @validates("permissions")
    def validate_permissions(self, value, **kwargs):
        for p in value:
            if not Permission.query.get(p):
                raise ValidationError(f"El permiso con ID {p} no existe.")
