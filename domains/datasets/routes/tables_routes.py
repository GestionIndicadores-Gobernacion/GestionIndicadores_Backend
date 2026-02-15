from flask_smorest import Blueprint, abort
from flask.views import MethodView

from domains.datasets.models.table import Table
from domains.datasets.models.dataset import Dataset
from domains.datasets.schemas.table_schema import TableSchema
from domains.datasets.validators.table_validator import (
    validate_dataset_is_active,
    validate_table_name
)
from extensions import db


blp = Blueprint(
    "tables",
    __name__,
    url_prefix="/tables",
    description="Gestión de tablas"
)

# =========================
# LISTAR / CREAR
# =========================
@blp.route("")
class TableListResource(MethodView):

    @blp.response(200, TableSchema(many=True))
    def get(self):
        return (
            Table.query
            .filter_by(active=True)
            .order_by(Table.created_at.desc())
            .all()
        )

    @blp.arguments(TableSchema)
    @blp.response(201, TableSchema)
    def post(self, data):
        dataset_id = data.get("dataset_id")

        if not dataset_id:
            abort(400, message="dataset_id es requerido")

        # Validaciones de dominio
        validate_dataset_is_active(dataset_id)
        validate_table_name(data["name"], dataset_id)

        table = Table(
            dataset_id=dataset_id,
            name=data["name"],
            description=data.get("description")
        )

        db.session.add(table)
        db.session.commit()
        return table


# =========================
# DETALLE / UPDATE / DELETE
# =========================
@blp.route("/<int:table_id>")
class TableResource(MethodView):

    @blp.response(200, TableSchema)
    def get(self, table_id):
        return Table.query.get_or_404(table_id)

    @blp.arguments(TableSchema(partial=True))
    @blp.response(200, TableSchema)
    def put(self, data, table_id):
        table = Table.query.get_or_404(table_id)

        if "dataset_id" in data:
            validate_dataset_is_active(data["dataset_id"])
            table.dataset_id = data["dataset_id"]

        if "name" in data:
            validate_table_name(data["name"], table.dataset_id, table_id)
            table.name = data["name"]

        if "description" in data:
            table.description = data["description"]

        db.session.commit()
        return table

    @blp.response(204)
    def delete(self, table_id):
        table = Table.query.get_or_404(table_id)

        db.session.delete(table)
        db.session.commit()
