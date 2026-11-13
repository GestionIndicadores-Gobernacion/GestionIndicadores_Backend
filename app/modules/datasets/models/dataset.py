from app.core.extensions import db
from datetime import datetime

class Dataset(db.Model):
    __tablename__ = "datasets"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, unique=True)
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    # Tipo de dashboard asignado al dataset (presupuesto, denuncias, ...).
    # Se fija al importar y se conserva en las actualizaciones mensuales para
    # que el dashboard no dependa de re-detectar columnas ni del nombre del
    # archivo. NULL = dataset anterior a esta columna (se detecta al vuelo).
    dataset_type = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    tables = db.relationship(
        "Table",
        back_populates="dataset",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
