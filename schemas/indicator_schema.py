from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import fields, validates, ValidationError
from extensions import db
from models.indicator import Indicator
from models.component import Component

class IndicatorSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Indicator
        load_instance = True
        sqla_session = db.session
        include_fk = True

    component_id = fields.Integer(required=True)
    name = fields.String(required=True)
    description = fields.String(allow_none=True)

    data_type = fields.String(required=True)
    required = fields.Boolean()
    use_list = fields.Boolean()
    allowed_values = fields.List(fields.String(), allow_none=True)
    active = fields.Boolean()

    # -------------------------
    # VALIDACIONES BÁSICAS
    # -------------------------

    @validates("component_id")
    def validate_component_id(self, value, **kwargs):
        if not Component.query.get(value):
            raise ValidationError("El componente indicado no existe.")

    @validates("name")
    def validate_name(self, value, **kwargs):
        if not value.strip():
            raise ValidationError("El nombre del indicador es obligatorio.")
        if len(value) < 3:
            raise ValidationError("Debe tener al menos 3 caracteres.")
        if len(value) > 200:
            raise ValidationError("Máximo 200 caracteres permitidos.")
        # ❗ No validar duplicados aquí (va en el route)

    @validates("data_type")
    def validate_data_type(self, value, **kwargs):
        allowed = ["integer", "decimal", "boolean", "text", "date", "category"]
        if value not in allowed:
            raise ValidationError(f"Tipo de dato inválido. Permitidos: {allowed}")

    @validates("allowed_values")
    def validate_allowed_values(self, value, **kwargs):
        if value is not None and not isinstance(value, list):
            raise ValidationError("allowed_values debe ser una lista de strings.")

        if value:
            for v in value:
                if not isinstance(v, str):
                    raise ValidationError("Todos los valores permitidos deben ser strings.")
