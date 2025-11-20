from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from models.role import Role
from schemas.permission_schema import PermissionSchema

class RoleSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Role
        load_instance = True
        include_relationships = True

    permissions = PermissionSchema(many=True)
