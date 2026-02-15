from domains.indicators.models.Strategy.strategy import Strategy
from extensions import db



class StrategyValidator:

    @staticmethod
    def validate_create(data):
        errors = {}

        for field in ['name', 'objective', 'product_goal_description']:
            if field not in data or not str(data[field]).strip():
                errors[field] = 'This field is required'

        goals = data.get('annual_goals')
        if not goals:
            errors['annual_goals'] = 'Annual goals are required'
            return errors

        years = set()

        for g in goals:
            year = g.get('year_number')
            value = g.get('value')

            if year in years:
                errors['annual_goals'] = 'Years cannot repeat'
            years.add(year)

            if year is None or year < 1:
                errors['annual_goals'] = 'Invalid year_number'

            if value is None or float(value) < 0:
                errors['annual_goals'] = 'Invalid value'

        exists = Strategy.query.filter_by(name=data['name']).first()
        if exists:
            errors['name'] = 'Strategy name already exists'

        return errors

