from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from models.permission import Permission

class PermissionSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Permission
        load_instance = True
