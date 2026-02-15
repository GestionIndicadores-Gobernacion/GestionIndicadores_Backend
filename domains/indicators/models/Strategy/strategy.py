from extensions import db
from datetime import datetime


class Strategy(db.Model):
    __tablename__ = 'strategies'

    id = db.Column(db.Integer, primary_key=True)

    # Nombre de la estrategia
    name = db.Column(db.String(255), nullable=False)

    # Objetivo de la estrategia
    objective = db.Column(db.Text, nullable=False)

    # Meta de producto asociada (descripción)
    product_goal_description = db.Column(db.Text, nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relación con metas anuales
    annual_goals = db.relationship(
        'StrategyAnnualGoal',
        back_populates='strategy',
        cascade='all, delete-orphan',
        lazy=True
    )

    # Relación existente
    components = db.relationship(
        'Component',
        back_populates='strategy',
        cascade='all, delete-orphan',
        lazy=True
    )
    
    reports = db.relationship(
        "Report",
        back_populates="strategy",
        cascade="all, delete-orphan",
        lazy=True
    )


    @property
    def total_goal(self):
        """TOTAL calculado dinámicamente"""
        return sum(goal.value for goal in self.annual_goals)

    def __repr__(self):
        return f"<Strategy {self.id} - {self.name}>"
