from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import fields
from extensions import db
from models.role import Role

class RoleSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Role
        load_instance = True
        sqla_session = db.session
        include_fk = True

    id = fields.Integer()
    name = fields.String()
    description = fields.String(allow_none=True)
