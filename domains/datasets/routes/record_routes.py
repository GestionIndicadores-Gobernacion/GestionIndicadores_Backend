from flask_smorest import Blueprint
from flask.views import MethodView
from flask import request

from domains.datasets.models.record import Record
from domains.datasets.models.table import Table
from domains.datasets.schemas.record_schema import RecordSchema
from domains.datasets.validators.record_validator import validate_record_data
from extensions import db

blp = Blueprint(
    "records",
    "records",
    url_prefix="/records",
    description="Registros de tablas"
)

# =========================
# LISTAR / CREAR RECORDS
# =========================
@blp.route("")
class RecordListResource(MethodView):

    @blp.response(200, RecordSchema(many=True))
    def get(self):
        table_id = request.args.get("table_id", type=int)

        query = Record.query

        if table_id:
            query = query.filter_by(table_id=table_id)

        return (
            query
            .order_by(Record.created_at.desc())
            .all()
        )

    @blp.arguments(RecordSchema)
    @blp.response(201, RecordSchema)
    def post(self, data):
        table = Table.query.get_or_404(data["table_id"])

        validate_record_data(table, data["data"])

        record = Record(
            table_id=data["table_id"],
            data=data["data"]
        )

        db.session.add(record)
        db.session.commit()
        return record

@blp.route("/<int:record_id>")
class RecordResource(MethodView):

    @blp.response(200, RecordSchema)
    def get(self, record_id):
        return Record.query.get_or_404(record_id)

    @blp.arguments(RecordSchema(partial=True))
    @blp.response(200, RecordSchema)
    def put(self, data, record_id):
        record = Record.query.get_or_404(record_id)
        table = record.table

        if "data" in data:
            validate_record_data(table, data["data"])
            record.data = data["data"]

        db.session.commit()
        return record

    @blp.response(204)
    def delete(self, record_id):
        record = Record.query.get_or_404(record_id)
        db.session.delete(record)
        db.session.commit()
