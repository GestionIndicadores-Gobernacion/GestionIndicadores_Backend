from marshmallow import fields, validates, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from models.indicator import Indicator
from models.component import Component
from extensions import db
import re

ALLOWED_TYPES = {"string", "integer", "boolean", "date", "float"}

class IndicatorSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Indicator
        load_instance = True
        sqla_session = db.session
        include_fk = True

    id = fields.Integer(dump_only=True)
    meta = fields.Float(required=True)
    
    @validates("component_id")
    def validate_component_id(self, value, **kwargs):
        if not Component.query.get(value):
            raise ValidationError("El componente indicado no existe.")

    @validates("name")
    def validate_name(self, value, **kwargs):
        if not value or not value.strip():
            raise ValidationError("El nombre es obligatorio.")

        if len(value) < 3:
            raise ValidationError("El nombre debe tener al menos 3 caracteres.")

        if len(value) > 150:
            raise ValidationError("El nombre no puede superar 150 caracteres.")

        if not re.match(r"^[A-Za-zÁÉÍÓÚáéíóúñÑ0-9 \-_]+$", value):
            raise ValidationError("El nombre contiene caracteres inválidos.")

    @validates("description")
    def validate_description(self, value, **kwargs):
        if value and len(value) > 500:
            raise ValidationError("La descripción no puede superar los 500 caracteres.")

    @validates("data_type")
    def validate_data_type(self, value, **kwargs):
        if value not in ALLOWED_TYPES:
            raise ValidationError(
                f"data_type debe ser uno de: {', '.join(ALLOWED_TYPES)}"
            )

    @validates("meta")
    def validate_meta(self, value, **kwargs):
        if value is None:
            raise ValidationError("El campo meta es obligatorio.")
        if value <= 0:
            raise ValidationError("La meta debe ser mayor a 0.")

    @validates("component_id")
    def validate_component_id(self, value, **kwargs):
        if not Component.query.get(value):
            raise ValidationError("El componente indicado no existe.")