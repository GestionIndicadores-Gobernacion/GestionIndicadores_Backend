from marshmallow import Schema, fields
from domains.indicators.schemas.strategy_schema import StrategySchema


class StrategyProgressSchema(Schema):
    current_year        = fields.Int()
    current_year_number = fields.Int(allow_none=True)
    current_year_goal   = fields.Float()
    current_year_actual = fields.Float()
    percent             = fields.Float()


class StrategyWithProgressSchema(StrategySchema):
    progress = fields.Nested(StrategyProgressSchema, dump_only=True)