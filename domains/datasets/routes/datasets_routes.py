from flask import jsonify
from flask_smorest import Blueprint
from flask.views import MethodView
from sqlalchemy import Table

from domains.datasets.models.dataset import Dataset
from domains.datasets.models.record import Record
from domains.datasets.models.table import Table
from domains.datasets.schemas.dataset_schema import DatasetSchema
from domains.datasets.validators.dataset_validator import validate_dataset_name
from extensions import db

blp = Blueprint(
    "datasets",
    __name__,
    url_prefix="/datasets",
    description="Gestión de datasets"
)

# =========================
# LISTAR / CREAR
# =========================
@blp.route("/")
class DatasetListResource(MethodView):

    @blp.response(200, DatasetSchema(many=True))
    def get(self):
        return Dataset.query.order_by(Dataset.created_at.desc()).all()

    @blp.arguments(DatasetSchema)
    @blp.response(201, DatasetSchema)
    def post(self, data):
        validate_dataset_name(data["name"])

        dataset = Dataset(
            name=data["name"],
            description=data.get("description")
        )

        db.session.add(dataset)
        db.session.commit()

        return dataset

@blp.route("/<int:dataset_id>")
class DatasetResource(MethodView):

    @blp.response(200, DatasetSchema)
    def get(self, dataset_id):
        return Dataset.query.get_or_404(dataset_id)

    @blp.arguments(DatasetSchema(partial=True))
    @blp.response(200, DatasetSchema)
    def put(self, data, dataset_id):
        dataset = Dataset.query.get_or_404(dataset_id)

        if "name" in data:
            validate_dataset_name(data["name"], dataset_id)
            dataset.name = data["name"]

        if "description" in data:
            dataset.description = data["description"]

        db.session.commit()
        return dataset

    @blp.response(204)
    def delete(self, dataset_id):
        dataset = Dataset.query.get_or_404(dataset_id)

        db.session.delete(dataset)   # 🔥 eliminación real
        db.session.commit()

@blp.route("/<int:dataset_id>/tables/<int:table_id>/records")
class DatasetTableRecordsResource(MethodView):

    @blp.response(200)
    def get(self, dataset_id, table_id):
        # Verificar que la tabla pertenece al dataset
        table = Table.query.filter_by(
            id=table_id,
            dataset_id=dataset_id
        ).first_or_404()

        records = Record.query.filter_by(table_id=table.id).all()

        return jsonify([
            {"id": r.id, "data": r.data}
            for r in records
        ])