from flask import jsonify
from flask_smorest import Blueprint
from flask.views import MethodView

from app.modules.datasets.models.table import Table
from app.modules.datasets.models.field import Field
from app.modules.datasets.models.record import Record
from .analyzer import analyze_dataset

blp = Blueprint("dataset_dashboard", __name__, url_prefix="/datasets")

@blp.route("/tables/<int:table_id>/dashboard")
class TableDashboardResource(MethodView):
    def get(self, table_id):
        table = Table.query.get_or_404(table_id)
        fields = Field.query.filter_by(table_id=table.id).all()
        records = Record.query.filter_by(table_id=table.id).all()

        dashboard = analyze_dataset(fields, records)
        dashboard["table"] = {
            "id": table.id,
            "name": table.name,
            "description": table.description,
            "dataset_id": table.dataset_id,
        }
        return jsonify(dashboard)