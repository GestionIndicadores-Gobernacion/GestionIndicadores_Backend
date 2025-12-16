from extensions import db
from datetime import datetime

class Record(db.Model):
    __tablename__ = "records"

    id = db.Column(db.Integer, primary_key=True)

    strategy_id = db.Column(
        db.Integer,
        db.ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True
    )

    activity_id = db.Column(
        db.Integer,
        db.ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True
    )

    component_id = db.Column(
        db.Integer,
        db.ForeignKey("components.id", ondelete="SET NULL"),
        nullable=True
    )

    fecha = db.Column(db.Date, nullable=False)

    # 🔥 NUEVO CAMPO
    description = db.Column(db.Text, nullable=True)

    actividades_realizadas = db.Column(db.Text, nullable=True)

    detalle_poblacion = db.Column(db.JSON, nullable=True)

    evidencia_url = db.Column(db.Text, nullable=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)


    # Relaciones
    strategy = db.relationship("Strategy", backref=db.backref("records", lazy=True))
    activity = db.relationship("Activity", backref=db.backref("records", lazy=True))
    component = db.relationship("Component", backref=db.backref("records", lazy=True))
