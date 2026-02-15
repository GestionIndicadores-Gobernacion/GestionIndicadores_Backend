from marshmallow import ValidationError
from domains.datasets.models.table import Table
from domains.datasets.models.dataset import Dataset
from extensions import db


def validate_table_name(
    name: str,
    dataset_id: int,
    table_id: int | None = None
):
    """
    Valida que el nombre de la tabla sea único dentro del dataset
    """

    if not name or not name.strip():
        raise ValidationError({"name": "El nombre es obligatorio"})

    query = Table.query.filter(
        Table.dataset_id == dataset_id,
        db.func.lower(Table.name) == name.lower()
    )

    if table_id:
        query = query.filter(Table.id != table_id)

    if query.first():
        raise ValidationError({
            "name": "Ya existe una tabla con este nombre en el dataset"
        })


def validate_dataset_is_active(dataset_id: int):
    """
    No permite crear tablas en datasets inactivos
    """

    dataset = Dataset.query.get(dataset_id)

    if not dataset:
        raise ValidationError({"dataset_id": "Dataset no existe"})

    if not dataset.active:
        raise ValidationError({
            "dataset": "No se pueden crear tablas en un dataset inactivo"
        })
