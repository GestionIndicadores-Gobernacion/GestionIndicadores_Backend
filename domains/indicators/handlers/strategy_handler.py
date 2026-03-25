from extensions import db

from domains.indicators.models.Strategy.strategy import Strategy
from domains.indicators.validators.strategy_validator import StrategyValidator
from domains.indicators.models.Strategy.strategy_annual_goal import StrategyAnnualGoal
from domains.indicators.models.Strategy.strategy_metric import StrategyMetric


class StrategyHandler:

    @staticmethod
    def create(data):
        errors = StrategyValidator.validate_create(data)
        if errors:
            return None, errors

        try:
            strategy = Strategy(
                name=data['name'],
                objective=data['objective'],
                product_goal_description=data['product_goal_description']
            )

            db.session.add(strategy)
            db.session.flush()  # obtener ID sin commit

            for goal in data['annual_goals']:
                db.session.add(
                    StrategyAnnualGoal(
                        strategy_id=strategy.id,
                        year_number=goal['year_number'],
                        value=goal['value']
                    )
                )
                
            for metric in data.get("metrics", []):
                db.session.add(
                    StrategyMetric(
                        strategy_id=strategy.id,
                        description=metric["description"],
                        metric_type=metric["metric_type"],
                        component_id=metric.get("component_id"),
                        field_name=metric.get("field_name"),
                        dataset_id=metric.get("dataset_id")  # ← agregar
                    )
                )

            db.session.commit()
            return strategy, None

        except Exception as e:
            db.session.rollback()
            return None, {"database": str(e)}


    @staticmethod
    def get_all():
        return Strategy.query.order_by(Strategy.created_at.desc()).all()

    @staticmethod
    def get_by_id(strategy_id):
        return Strategy.query.get(strategy_id)

    @staticmethod
    def update(strategy, data):

        # ----------------------------
        # actualizar campos base
        # ----------------------------
        for field in ['name', 'objective', 'product_goal_description']:
            if field in data:
                setattr(strategy, field, data[field])

        # ----------------------------
        # sincronizar metas anuales
        # ----------------------------
        if 'annual_goals' in data:

            StrategyAnnualGoal.query.filter_by(
                strategy_id=strategy.id
            ).delete()

            db.session.flush()

            for goal in data['annual_goals']:
                db.session.add(
                    StrategyAnnualGoal(
                        strategy_id=strategy.id,
                        year_number=goal['year_number'],
                        value=goal['value']
                    )
                )

        # ----------------------------
        # sincronizar métricas
        # ----------------------------
        if 'metrics' in data:

            StrategyMetric.query.filter_by(
                strategy_id=strategy.id
            ).delete()

            db.session.flush()

            for metric in data['metrics']:
                db.session.add(
                    StrategyMetric(
                    strategy_id=strategy.id,
                    description=metric["description"],
                    metric_type=metric["metric_type"],
                    component_id=metric.get("component_id"),
                    field_name=metric.get("field_name"),
                    dataset_id=metric.get("dataset_id")  # ← agregar
                )
            )

        db.session.commit()
        return strategy
    
    @staticmethod
    def delete(strategy):
        db.session.delete(strategy)
        db.session.commit()
