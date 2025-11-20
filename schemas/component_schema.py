from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from models.component import Component

class ComponentSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Component
        load_instance = True
