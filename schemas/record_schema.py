from marshmallow import fields, validates, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema

from models.record import Record
from models.strategy import Strategy
from models.component import Component
from models.indicator import Indicator

from extensions import db


class RecordSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Record
        load_instance = True
        sqla_session = db.session
        include_fk = True

    # Campos explícitos
    id = fields.Integer(dump_only=True)
    strategy_id = fields.Integer(required=True)        # 👈 NUEVO
    component_id = fields.Integer(required=True)

    municipio = fields.String(required=True)
    fecha = fields.Date(required=True)

    detalle_poblacion = fields.Dict(allow_none=True)

    evidencia_url = fields.String(allow_none=True)

    # =======================================================
    # 🔎 VALIDACIONES
    # =======================================================

    @validates("strategy_id")
    def validate_strategy_id(self, value, **kwargs):
        if not Strategy.query.get(value):
            raise ValidationError("La estrategia indicada no existe.")

    @validates("component_id")
    def validate_component_id(self, value, **kwargs):
        if not Component.query.get(value):
            raise ValidationError("El componente indicado no existe.")

    @validates("municipio")
    def validate_municipio(self, value, **kwargs):
        if not value.strip():
            raise ValidationError("El municipio es obligatorio.")