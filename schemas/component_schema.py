from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import fields, validates, ValidationError
from extensions import db
from models.component import Component

class ComponentSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Component
        load_instance = True
        sqla_session = db.session
        include_fk = True

    name = fields.String(required=True)
    description = fields.String(allow_none=True)
    active = fields.Boolean(
        required=False,
        allow_none=False,
        load_default=True,
        dump_default=True
    )


    # -------------------------
    # VALIDACIONES BÁSICAS
    # -------------------------
    @validates("name")
    def validate_name(self, value, **kwargs):
        if not value or value.strip() == "":
            raise ValidationError("El nombre del componente es obligatorio.")

        if len(value) < 3:
            raise ValidationError("Debe tener al menos 3 caracteres.")

        if len(value) > 150:
            raise ValidationError("Máximo 150 caracteres permitidos.")


    @validates("description")
    def validate_description(self, value, **kwargs):
        if value and len(value) < 5:
            raise ValidationError("La descripción debe tener mínimo 5 caracteres si se envía.")
