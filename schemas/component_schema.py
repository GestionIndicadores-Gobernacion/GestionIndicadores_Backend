from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import fields, validates, ValidationError
from extensions import db
from models.component import Component
from models.strategy import Strategy

TIPOS_VALIDOS = ["integer", "decimal", "boolean", "text", "date", "category"]

class ComponentSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Component
        load_instance = True
        sqla_session = db.session
        include_fk = True

    id = fields.Integer(dump_only=True)

    # IMPORTANTE: estos nombres deben coincidir con los campos reales del modelo
    strategy_id = fields.Integer(required=True)
    name = fields.String(required=True)
    data_type = fields.String(required=True)
    active = fields.Boolean()

    @validates("strategy_id")
    def validate_strategy_id(self, value, **kwargs):
        if not Strategy.query.get(value):
            raise ValidationError("La estrategia indicada no existe.")

    @validates("name")
    def validate_name(self, value, **kwargs):
        if not value.strip():
            raise ValidationError("El nombre es obligatorio.")
        if len(value) < 3:
            raise ValidationError("El nombre debe tener mínimo 3 caracteres.")

    @validates("data_type")
    def validate_data_type(self, value, **kwargs):
        if value not in TIPOS_VALIDOS:
            raise ValidationError(
                f"tipo_dato inválido. Debe ser uno de: {TIPOS_VALIDOS}"
            )
