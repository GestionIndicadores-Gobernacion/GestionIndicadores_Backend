from marshmallow import fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from models.record import Record

class RecordSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Record
        load_instance = True
        include_fk = True

    fecha = fields.Date(required=True)
    municipio = fields.String(required=True, validate=validate.Length(min=1))
    tipo_poblacion = fields.String(required=True)
    detalle_poblacion = fields.Dict(keys=fields.String(), values=fields.Integer(), required=False)
    valor = fields.String(required=False, allow_none=True)
    evidencia_url = fields.Url(required=False, allow_none=True)
    creado_por = fields.String(required=False)
    fecha_registro = fields.DateTime(dump_only=True)
