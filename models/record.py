from datetime import datetime
from extensions import db

class Record(db.Model):
    __tablename__ = "records"

    id = db.Column(db.Integer, primary_key=True)

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

    # 👇 CAMBIAR A JSON PARA ACEPTAR LISTAS ["Perros","Gatos"]
    tipo_poblacion = db.Column(db.JSON, nullable=False)

    # {"Perros": 8, "Gatos": 12}
    detalle_poblacion = db.Column(db.JSON, nullable=True)

    valor = db.Column(db.Text, nullable=True)
    evidencia_url = db.Column(db.Text, nullable=True)
    creado_por = db.Column(db.String(120), nullable=True)

    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    component = db.relationship("Component", backref=db.backref("records", lazy=True))
    indicator = db.relationship("Indicator", backref=db.backref("records", lazy=True))
