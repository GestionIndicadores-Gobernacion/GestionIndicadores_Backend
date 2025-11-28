from marshmallow import fields, validates, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from extensions import db
from models.strategy import Strategy
import re

class StrategySchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Strategy
        load_instance = True
        sqla_session = db.session
        include_fk = True
        partial = True

    id = fields.Integer(dump_only=True)

    @validates("name")
    def validate_name(self, value, **kwargs):
        if not value or not value.strip():
            raise ValidationError("El nombre es obligatorio.")

        if len(value) < 3:
            raise ValidationError("El nombre debe tener al menos 3 caracteres.")

        if len(value) > 150:
            raise ValidationError("El nombre no puede superar los 150 caracteres.")

        if not re.match(r"^[A-Za-zÁÉÍÓÚáéíóúñÑ0-9 \-\_]+$", value):
            raise ValidationError("El nombre contiene caracteres inválidos.")

    @validates("description")
    def validate_description(self, value, **kwargs):
        if value and len(value) > 500:
            raise ValidationError("La descripción no puede superar 500 caracteres.")
