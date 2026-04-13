from app.core.extensions import db
from datetime import datetime


class Strategy(db.Model):
    __tablename__ = 'strategies'

    id = db.Column(db.Integer, primary_key=True)

    name                     = db.Column(db.String(255), nullable=False)
    objective                = db.Column(db.Text, nullable=False)
    product_goal_description = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # lazy='subquery' → carga la relación en la misma query, evita el problema
    # de sesión cerrada al serializar con marshmallow
    annual_goals = db.relationship(
        'StrategyAnnualGoal',
        back_populates='strategy',
        cascade='all, delete-orphan',
        lazy='subquery'   # ← era lazy=True
    )

    metrics = db.relationship(
        "StrategyMetric",
        back_populates="strategy",
        cascade="all, delete-orphan",
        lazy='subquery'   # ← era lazy=True
    )

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
        return sum((goal.value or 0) for goal in self.annual_goals)

    def __repr__(self):
        return f"<Strategy {self.id} - {self.name}>"