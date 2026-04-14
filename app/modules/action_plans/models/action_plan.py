from app.core.extensions import db
from datetime import datetime, date


class ActionPlanResponsibleUser(db.Model):
    """Tabla de múltiples responsables por plan de acción."""
    __tablename__ = "action_plan_responsible_users"

    id             = db.Column(db.Integer, primary_key=True)
    action_plan_id = db.Column(db.Integer, db.ForeignKey("action_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    user = db.relationship("User", foreign_keys=[user_id], lazy="select")

    __table_args__ = (
        db.UniqueConstraint("action_plan_id", "user_id", name="uq_plan_responsible_user"),
    )

    def __repr__(self):
        return f"<ActionPlanResponsibleUser plan={self.action_plan_id} user={self.user_id}>"


class ActionPlan(db.Model):
    __tablename__ = "action_plans"

    id           = db.Column(db.Integer, primary_key=True)
    strategy_id  = db.Column(db.Integer, db.ForeignKey("strategies.id",  ondelete="CASCADE"), nullable=False)
    component_id = db.Column(db.Integer, db.ForeignKey("components.id",  ondelete="CASCADE"), nullable=False)

    # ── Responsable (legacy — se mantiene para compatibilidad) ───────────
    responsible = db.Column(db.String(255), nullable=True)  # texto display (legacy/opcional)
    responsible_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # ── Creador ──────────────────────────────────────────────────────────
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # ── Relaciones ───────────────────────────────────────────────────────
    strategy  = db.relationship("Strategy",  backref=db.backref("action_plans", lazy=True))
    component = db.relationship("Component", backref=db.backref("action_plans", lazy=True))

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("action_plans_created", lazy=True)
    )

    responsible_user = db.relationship(
        "User",
        foreign_keys=[responsible_user_id],
        backref=db.backref("action_plans_assigned", lazy=True)
    )

    plan_objectives = db.relationship(
        "ActionPlanObjective",
        back_populates="action_plan",
        cascade="all, delete-orphan",
        lazy=True
    )

    # ── Múltiples responsables ───────────────────────────────────────────
    responsible_users = db.relationship(
        "ActionPlanResponsibleUser",
        backref=db.backref("action_plan", lazy="select"),
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    @property
    def total_score(self):
        total = 0
        for obj in self.plan_objectives:
            for act in obj.activities:
                try:
                    total += act.computed_score
                except Exception:
                    total += act.score or 0
        return total

    @property
    def responsible_display(self):
        """Retorna el nombre del responsable: múltiples usuarios, usuario único, o texto libre."""
        if self.responsible_users:
            names = []
            for ru in self.responsible_users:
                if ru.user:
                    names.append(f"{ru.user.first_name} {ru.user.last_name}")
            if names:
                return ", ".join(names)
        if self.responsible_user:
            return f"{self.responsible_user.first_name} {self.responsible_user.last_name}"
        return self.responsible or "Sin asignar"

    @property
    def responsible_user_ids(self):
        """Lista de IDs de responsables (nuevo sistema)."""
        if self.responsible_users:
            return [ru.user_id for ru in self.responsible_users]
        # Fallback al campo legacy
        if self.responsible_user_id:
            return [self.responsible_user_id]
        return []

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
    lugar                    = db.Column(db.String(255), nullable=True)
    requires_boss_assistance = db.Column(db.Boolean, default=False, nullable=False)

    evidence_url = db.Column(db.String(500), nullable=True)
    description  = db.Column(db.Text, nullable=True)
    reported_at  = db.Column(db.DateTime, nullable=True)
    score        = db.Column(db.Integer, nullable=True)
    generates_report = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    plan_objective = db.relationship("ActionPlanObjective", back_populates="activities")

    reported_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    recurrence_group_id = db.Column(db.String(36), nullable=True, index=True)
    recurrence_rule     = db.Column(db.JSON, nullable=True)

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
    
    @property
    def computed_score(self) -> int | None:
        """
        Reglas:
        - Sin evidence_url + fecha futura (En Ejecución) → None (no suma ni resta)
        - Sin evidence_url + fecha pasada (Pendiente vencida) → -1
        - Con evidence_url (Realizado) → 5
        - Con evidence_url + generates_report + reporte vinculado → 7
        """
        if not self.evidence_url:
            if date.today() <= self.delivery_date:
                return None   # En Ejecución — no puntuar
            return -1         # Pendiente vencida

        base = 5
        try:
            if self.generates_report and self.linked_report is not None:
                base += 2
        except Exception:
            pass

        return base

class ActionPlanSupportStaff(db.Model):
    __tablename__ = "action_plan_support_staff"

    id          = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("action_plan_activities.id", ondelete="CASCADE"), nullable=False)
    name        = db.Column(db.String(255), nullable=False)
    # Vínculo opcional con usuario existente en la plataforma
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    activity = db.relationship("ActionPlanActivity", back_populates="support_staff")
    user     = db.relationship("User", foreign_keys=[user_id], lazy="select",
                               backref=db.backref("support_staff_assignments", lazy=True))

    def __repr__(self):
        return f"<ActionPlanSupportStaff {self.id} - {self.name}>"