from datetime import datetime
from db import db

class Record(db.Model):
    __tablename__ = "records"

    id = db.Column(db.Integer, primary_key=True)

    # Referencias
    component_id = db.Column(
        db.Integer,
        db.ForeignKey("components.id", ondelete="SET NULL"),
        nullable=True
    )
    indicator_id = db.Column(
        db.Integer,
        db.ForeignKey("indicators.id", ondelete="SET NULL"),
        nullable=True
    )

    municipio = db.Column(db.String(150), nullable=False)
    fecha = db.Column(db.Date, nullable=False)
    tipo_poblacion = db.Column(db.String(100), nullable=False)
    detalle_poblacion = db.Column(db.JSON, nullable=True)  # ej: {"perros": 8, "gatos": 12}

    valor = db.Column(db.Text, nullable=True)       # valor textual o numérico según indicador
    evidencia_url = db.Column(db.Text, nullable=True)

    creado_por = db.Column(db.String(120), nullable=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    # relaciones
    component = db.relationship("Component", backref=db.backref("records", lazy=True))
    indicator = db.relationship("Indicator", backref=db.backref("records", lazy=True))
