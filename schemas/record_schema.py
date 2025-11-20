from marshmallow import fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from models.record import Record
from extensions import db

class RecordSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Record
        load_instance = False
        include_fk = True
        sqla_session = db.session

    fecha = fields.Date(required=True)
    municipio = fields.String(required=True, validate=validate.Length(min=1))

    # 🔥 ACEPTA STRING O LISTA
    tipo_poblacion = fields.Raw(required=True)

    detalle_poblacion = fields.Dict(
        keys=fields.String(),
        values=fields.Integer(),
        allow_none=True
    )

    valor = fields.String(allow_none=True)
    evidencia_url = fields.Url(allow_none=True)

    creado_por = fields.String(allow_none=True)
    fecha_registro = fields.DateTime(dump_only=True)
