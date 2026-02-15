from marshmallow import ValidationError
from domains.datasets.models.dataset import Dataset
from extensions import db


def validate_dataset_name(name: str, dataset_id: int | None = None):
    """
    Valida que el nombre del dataset sea único (case-insensitive)
    """

    if not name or not name.strip():
        raise ValidationError({"name": "El nombre es obligatorio"})

    query = Dataset.query.filter(
        db.func.lower(Dataset.name) == name.lower()
    )

    if dataset_id:
        query = query.filter(Dataset.id != dataset_id)

    if query.first():
        raise ValidationError({
            "name": "Ya existe un dataset con este nombre"
        })
