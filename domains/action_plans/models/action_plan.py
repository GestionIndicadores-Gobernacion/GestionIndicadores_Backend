from extensions import db
from datetime import datetime, date


class ActionPlan(db.Model):
    __tablename__ = "action_plans"

    id           = db.Column(db.Integer, primary_key=True)
    strategy_id  = db.Column(db.Integer, db.ForeignKey("strategies.id",  ondelete="CASCADE"), nullable=False)
    component_id = db.Column(db.Integer, db.ForeignKey("components.id",  ondelete="CASCADE"), nullable=False)
    responsible  = db.Column(db.String(255), nullable=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    strategy  = db.relationship("Strategy",  backref=db.backref("action_plans", lazy=True))
    component = db.relationship("Component", backref=db.backref("action_plans", lazy=True))
    user      = db.relationship("User",      backref=db.backref("action_plans_created", lazy=True))

    plan_objectives = db.relationship(
        "ActionPlanObjective",
        back_populates="action_plan",
        cascade="all, delete-orphan",
        lazy=True
    )

    @property
    def total_score(self):
        total = 0
        for obj in self.plan_objectives:
            for act in obj.activities:
                if act.score is not None:
                    total += act.score
        return total

    def __repr__(self):
        return f"<ActionPlan {self.id}>"


class ActionPlanObjective(db.Model):
    __tablename__ = "action_plan_objectives"

    id             = db.Column(db.Integer, primary_key=True)
    action_plan_id = db.Column(db.Integer, db.ForeignKey("action_plans.id", ondelete="CASCADE"), nullable=False)
    objective_id   = db.Column(db.Integer, db.ForeignKey("component_objectives.id", ondelete="SET NULL"), nullable=True)
    objective_text = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    action_plan = db.relationship("ActionPlan", back_populates="plan_objectives")
    objective   = db.relationship("ComponentObjective", backref=db.backref("plan_objectives", lazy=True))

    activities = db.relationship(
        "ActionPlanActivity",
        back_populates="plan_objective",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<ActionPlanObjective {self.id}>"


class ActionPlanActivity(db.Model):
    __tablename__ = "action_plan_activities"

    id                       = db.Column(db.Integer, primary_key=True)
    plan_objective_id        = db.Column(db.Integer, db.ForeignKey("action_plan_objectives.id", ondelete="CASCADE"), nullable=False)
    name                     = db.Column(db.String(500), nullable=False)
    deliverable              = db.Column(db.Text, nullable=False)
    delivery_date            = db.Column(db.Date, nullable=False)
    lugar = db.Column(db.String(255), nullable=True)
    requires_boss_assistance = db.Column(db.Boolean, default=False, nullable=False)

    evidence_url = db.Column(db.String(500), nullable=True)
    description  = db.Column(db.Text, nullable=True)
    reported_at  = db.Column(db.DateTime, nullable=True)
    score        = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    plan_objective = db.relationship("ActionPlanObjective", back_populates="activities")

    reported_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    ) 
    
    recurrence_group_id = db.Column(
        db.String(36),  # UUID como string
        nullable=True,
        index=True
    )   
    
    recurrence_rule = db.Column(
        db.JSON,  # guarda la regla: {"frequency": "monthly", "day": 26, "until": "2026-12-31"}
        nullable=True
    )
    
    reported_by = db.relationship(
        "User",
        foreign_keys=[reported_by_user_id],
        backref=db.backref("activities_reported", lazy=True)
    )

    support_staff = db.relationship(
        "ActionPlanSupportStaff",
        back_populates="activity",
        cascade="all, delete-orphan",
        lazy=True
    )

    @property
    def status(self):
        if self.evidence_url:
            return "Realizado"
        if date.today() < self.delivery_date:
            return "En Ejecución"
        return "Pendiente"

    def __repr__(self):
        return f"<ActionPlanActivity {self.id} - {self.status}>"


class ActionPlanSupportStaff(db.Model):
    __tablename__ = "action_plan_support_staff"

    id          = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("action_plan_activities.id", ondelete="CASCADE"), nullable=False)
    name        = db.Column(db.String(255), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    activity = db.relationship("ActionPlanActivity", back_populates="support_staff")

    def __repr__(self):
        return f"<ActionPlanSupportStaff {self.id} - {self.name}>"