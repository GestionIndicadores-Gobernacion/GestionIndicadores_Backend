from flask import jsonify
from flask_smorest import Blueprint
from flask.views import MethodView

from app.modules.datasets.models.table import Table
from app.modules.datasets.models.field import Field
from app.modules.datasets.models.record import Record

blp = Blueprint(
    "dataset_viewer",
    __name__,
    url_prefix="/datasets"
)


@blp.route("/tables/<int:table_id>/viewer")
class TableViewerResource(MethodView):

    def get(self, table_id):
        table = Table.query.get_or_404(table_id)

        fields = Field.query.filter_by(table_id=table.id).all()
        records = Record.query.filter_by(table_id=table.id).all()

        return jsonify({
            "table": {
                "id": table.id,
                "name": table.name,
                "description": table.description,
                "dataset_id": table.dataset_id,
            },
            "fields": [
                {
                    "id": f.id,
                    "name": f.name,
                    "label": f.label,
                    "type": f.type,
                }
                for f in fields
            ],
            "records": [
                {"id": r.id, "data": r.data}
                for r in records
            ],
            "total": len(records)
        })