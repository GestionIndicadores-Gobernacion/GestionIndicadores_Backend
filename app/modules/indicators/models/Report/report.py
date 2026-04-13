from datetime import datetime
import enum
from app.core.extensions import db


class ZoneTypeEnum(enum.Enum):
    URBANA = "Urbana"
    RURAL  = "Rural"


class Report(db.Model):
    __tablename__ = "reports"

    id           = db.Column(db.Integer, primary_key=True)
    strategy_id  = db.Column(db.Integer, db.ForeignKey("strategies.id",  ondelete="CASCADE"), nullable=False, index=True)
    component_id = db.Column(db.Integer, db.ForeignKey("components.id",  ondelete="CASCADE"), nullable=False, index=True)
    report_date  = db.Column(db.Date,    nullable=False, index=True)

    executive_summary    = db.Column(db.Text,        nullable=False)
    intervention_location = db.Column(db.String(255), nullable=False)
    zone_type            = db.Column(db.Enum(ZoneTypeEnum), nullable=False)
    evidence_link        = db.Column(db.Text,        nullable=True)

    # ── NUEVO ──────────────────────────────────────────────────────
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    # ───────────────────────────────────────────────────────────────

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    strategy   = db.relationship("Strategy",  back_populates="reports")
    component  = db.relationship("Component", back_populates="reports")
    user       = db.relationship("User",      backref=db.backref("reports", lazy=True))

    indicator_values = db.relationship(
        "ReportIndicatorValue",
        back_populates="report",
        cascade="all, delete-orphan"
    )
    
    action_plan_activity_id = db.Column(
        db.Integer,
        db.ForeignKey("action_plan_activities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        unique=True   # una actividad → máximo un reporte
    )
    
    activity = db.relationship(
        "ActionPlanActivity",
        backref=db.backref("linked_report", uselist=False, lazy="select"),
        foreign_keys=[action_plan_activity_id]
    )

    def __repr__(self):
        return f"<Report {self.id} - {self.report_date}>"