from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from models.indicator import Indicator

class IndicatorSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Indicator
        load_instance = True
        include_fk = True
