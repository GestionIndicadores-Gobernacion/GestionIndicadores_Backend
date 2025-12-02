from marshmallow import fields, validates, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from extensions import db
from models.record import Record
from models.strategy import Strategy
from models.component import Component


class RecordSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Record
        load_instance = True
        sqla_session = db.session
        include_fk = True

    id = fields.Integer(dump_only=True)
    strategy_id = fields.Integer(required=True)
    component_id = fields.Integer(required=True)

    fecha = fields.Date(required=True)

    # JSON complejo
    detalle_poblacion = fields.Dict(required=True)

    evidencia_url = fields.String(allow_none=True)

    # ===============================
    # VALIDACIONES
    # ===============================

    @validates("strategy_id")
    def validate_strategy_id(self, value, **kwargs):
        if not Strategy.query.get(value):
            raise ValidationError("La estrategia indicada no existe.")

    @validates("component_id")
    def validate_component_id(self, value, **kwargs):
        if not Component.query.get(value):
            raise ValidationError("El componente indicado no existe.")

    @validates("detalle_poblacion")
    def validate_detalle_poblacion(self, value, **kwargs):
        if not isinstance(value, dict):
            raise ValidationError("detalle_poblacion debe ser un objeto JSON.")

        if "municipios" not in value:
            raise ValidationError("detalle_poblacion debe incluir la clave 'municipios'.")

        municipios = value["municipios"]

        if not isinstance(municipios, dict):
            raise ValidationError("'municipios' debe ser un diccionario.")

        for municipio, info in municipios.items():
            if not isinstance(municipio, str):
                raise ValidationError("Cada municipio debe ser string.")

            if not isinstance(info, dict) or "indicadores" not in info:
                raise ValidationError(
                    f"El municipio '{municipio}' debe contener 'indicadores'."
                )

            indicadores = info["indicadores"]

            if not isinstance(indicadores, dict):
                raise ValidationError(
                    f"'indicadores' en municipio '{municipio}' debe ser un diccionario."
                )

            for indicador, valor in indicadores.items():
                if not isinstance(indicador, str):
                    raise ValidationError(
                        "Las claves de indicadores deben ser strings."
                    )

                if not isinstance(valor, int) or valor < 0:
                    raise ValidationError(
                        f"El valor del indicador '{indicador}' en '{municipio}' debe ser un entero >= 0."
                    )
