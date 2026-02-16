from extensions import db


class StrategyAnnualGoal(db.Model):
    __tablename__ = 'strategy_annual_goals'

    id = db.Column(db.Integer, primary_key=True)

    strategy_id = db.Column(
        db.Integer,
        db.ForeignKey('strategies.id', ondelete='CASCADE'),
        nullable=False
    )

    # Año lógico del plan (1,2,3,4...)
    year_number = db.Column(db.Integer, nullable=False)

    # Valor de la meta para ese año
    value = db.Column(db.Numeric(14, 2), nullable=False)

    strategy = db.relationship(
        'Strategy',
        back_populates='annual_goals'
    )

    __table_args__ = (
        db.UniqueConstraint('strategy_id', 'year_number',
                            name='uq_strategy_year'),
    )

    def __repr__(self):
        return f"<StrategyAnnualGoal Strategy:{self.strategy_id} Year:{self.year_number}>"
