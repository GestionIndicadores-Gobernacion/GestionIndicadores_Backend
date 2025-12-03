from marshmallow import fields, validates, ValidationError
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from extensions import db
from models.activity import Activity

class ActivitySchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Activity
        load_instance = True
        sqla_session = db.session
        include_fk = True
        partial = True

    id = fields.Integer(dump_only=True)

    description = fields.String(required=True)

    @validates("description")
    def validate_description(self, value, **kwargs):
        if not value or not value.strip():
            raise ValidationError("La descripción es obligatoria.")

        if len(value) < 3:
            raise ValidationError("Debe tener al menos 3 caracteres.")

        if len(value) > 500:
            raise ValidationError("La descripción no puede superar 500 caracteres.")
