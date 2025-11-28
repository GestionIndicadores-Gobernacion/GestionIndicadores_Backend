from extensions import db
from datetime import datetime

class Record(db.Model):
    __tablename__ = "records"

    id = db.Column(db.Integer, primary_key=True)

    # ← ESTO ES OBLIGATORIO
    strategy_id = db.Column(
        db.Integer,
        db.ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True
    )

    component_id = db.Column(
        db.Integer,
        db.ForeignKey("components.id", ondelete="SET NULL"),
        nullable=True
    )

    municipio = db.Column(db.String(150), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    detalle_poblacion = db.Column(db.JSON, nullable=True)
    evidencia_url = db.Column(db.Text, nullable=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    # relaciones
    strategy = db.relationship("Strategy", backref=db.backref("records", lazy=True))
    component = db.relationship("Component", backref=db.backref("records", lazy=True))
