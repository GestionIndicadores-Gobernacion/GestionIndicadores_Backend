from marshmallow import fields, validates, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from extensions import db

from models.record import Record
from models.strategy import Strategy
from models.component import Component
from models.activity import Activity


class RecordSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Record
        load_instance = True
        sqla_session = db.session
        include_fk = True

    id = fields.Integer(dump_only=True)

    # 🔥 backend los deriva, pero siguen existiendo
    strategy_id = fields.Integer(dump_only=True)
    activity_id = fields.Integer(dump_only=True)
    component_id = fields.Integer(required=True)


    fecha = fields.Date(required=True)
    description = fields.String(allow_none=True)
    actividades_realizadas = fields.String(allow_none=True)

    detalle_poblacion = fields.Dict(required=True)
    evidencia_url = fields.String(allow_none=True)

    # ===============================
    # VALIDACIONES BÁSICAS
    # ===============================
    @validates("strategy_id")
    def validate_strategy_id(self, value, **kwargs):
        if not Strategy.query.get(value):
            raise ValidationError("La estrategia indicada no existe.")

    @validates("activity_id")
    def validate_activity_id(self, value, **kwargs):
        if not Activity.query.get(value):
            raise ValidationError("La actividad indicada no existe.")

    @validates("component_id")
    def validate_component_id(self, value, **kwargs):
        if not Component.query.get(value):
            raise ValidationError("El componente indicado no existe.")
