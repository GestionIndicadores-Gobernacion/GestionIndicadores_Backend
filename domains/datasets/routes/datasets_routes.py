from flask_smorest import Blueprint
from flask.views import MethodView

from domains.datasets.models.dataset import Dataset
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
