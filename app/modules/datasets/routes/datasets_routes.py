from flask import jsonify
from flask_jwt_extended import jwt_required
from flask_smorest import Blueprint
from flask.views import MethodView
from sqlalchemy import Table

from app.modules.datasets.models.dataset import Dataset
from app.modules.datasets.models.field import Field
from app.modules.datasets.models.record import Record
from app.modules.datasets.models.table import Table
from app.modules.datasets.schemas.dataset_schema import DatasetSchema
from app.modules.datasets.validators.dataset_validator import validate_dataset_name
from app.core.extensions import db

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
    decorators = [jwt_required()]

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

# =========================
# DETALLE / UPDATE / DELETE
# =========================
@blp.route("/<int:dataset_id>")
class DatasetResource(MethodView):
    decorators = [jwt_required()]

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
        db.session.delete(dataset)
        db.session.commit()

# =========================
# RECORDS DE TODAS LAS TABLAS DEL DATASET
# GET /datasets/:id/records
# Usado por indicadores dataset_select para listar opciones
# =========================
@blp.route("/<int:dataset_id>/records")
class DatasetRecordsResource(MethodView):
    decorators = [jwt_required()]

    def get(self, dataset_id):
        dataset = Dataset.query.get_or_404(dataset_id)

        # Obtener todas las tablas activas del dataset
        tables = Table.query.filter_by(
            dataset_id=dataset_id,
            active=True
        ).all()

        table_ids = [t.id for t in tables]

        if not table_ids:
            return jsonify([])

        records = (
            Record.query
            .filter(Record.table_id.in_(table_ids))
            .order_by(Record.id.asc())
            .all()
        )

        return jsonify([
            {"id": r.id, "data": r.data}
            for r in records
        ])

# =========================
# RECORDS POR TABLA ESPECÍFICA
# GET /datasets/:id/tables/:table_id/records
# =========================
@blp.route("/<int:dataset_id>/tables/<int:table_id>/records")
class DatasetTableRecordsResource(MethodView):
    decorators = [jwt_required()]

    def get(self, dataset_id, table_id):
        table = Table.query.filter_by(
            id=table_id,
            dataset_id=dataset_id
        ).first_or_404()

        records = Record.query.filter_by(table_id=table.id).all()

        return jsonify([
            {"id": r.id, "data": r.data}
            for r in records
        ])
        
        
# =========================
# EXPLORER DE TABLA (schema + rows)
# GET /datasets/:dataset_id/tables/:table_id/explore
# =========================
@blp.route("/tables/<int:table_id>/explore")
class TableExplorerResource(MethodView):
    decorators = [jwt_required()]

    def get(self, table_id):

        table = Table.query.get_or_404(table_id)

        fields = Field.query.filter_by(table_id=table.id).all()
        records = Record.query.filter_by(table_id=table.id).limit(500).all()

        return {
            "table": {
                "id": table.id,
                "name": table.name,
                "description": table.description
            },
            "fields": [
                {
                    "name": f.name,
                    "label": f.label,
                    "type": f.type
                }
                for f in fields
            ],
            "rows": [r.data for r in records],
            "total": Record.query.filter_by(table_id=table.id).count()
        }

# =========================
# RECORDS FILTRADOS POR MUNICIPIO
# GET /datasets/:dataset_id/records/by-municipio/<municipio>
# Usado por dataset_select para filtrar actores por municipio
# =========================
@blp.route("/<int:dataset_id>/records/by-municipio/<string:municipio>")
class DatasetRecordsByMunicipioResource(MethodView):
    decorators = [jwt_required()]

    def get(self, dataset_id, municipio):

        dataset = Dataset.query.get_or_404(dataset_id)

        tables = Table.query.filter_by(
            dataset_id=dataset_id,
            active=True
        ).all()

        table_ids = [t.id for t in tables]

        if not table_ids:
            return jsonify([])

        records = (
            Record.query
            .filter(Record.table_id.in_(table_ids))
            .order_by(Record.id.asc())
            .all()
        )

        municipio = municipio.lower().strip()

        filtered = []

        for r in records:
            record_municipio = str(r.data.get("municipio", "")).lower()

            if record_municipio == municipio:
                filtered.append({
                    "id": r.id,
                    "data": r.data
                })

        return jsonify(filtered)