import pandas as pd
from flask import request
from flask_smorest import Blueprint
from flask.views import MethodView

from domains.datasets.models.table import Table
from domains.datasets.models.record import Record
from domains.datasets.validators.record_validator import validate_record_data
from extensions import db

blp = Blueprint(
    "record_import",
    __name__,
    url_prefix="/records",
    description="Importación de registros desde Excel"
)

def map_excel_row_to_record(table, row: dict) -> dict:
    """
    Mapea columnas del Excel (label humano) a Field.name
    """

    # label normalizado -> field.name
    label_to_name = {
        field.label.strip().lower(): field.name
        for field in table.fields
    }

    record_data = {}

    for column_label, value in row.items():
        if value is None:
            continue

        key = str(column_label).strip().lower()

        if key in label_to_name:
            record_data[label_to_name[key]] = value

    return record_data

@blp.route("/import")
class RecordImportResource(MethodView):

    @blp.response(200)
    def post(self):
        # =========================
        # INPUT
        # =========================
        table_id = request.form.get("table_id", type=int)

        if not table_id:
            return {"error": "table_id es requerido"}, 400

        table = Table.query.get_or_404(table_id)

        if "file" not in request.files:
            return {"error": "Archivo no enviado"}, 400

        file = request.files["file"]

        # =========================
        # READ EXCEL
        # =========================
        try:
            df = pd.read_excel(file)
        except Exception:
            return {"error": "Archivo Excel inválido"}, 400

        inserted = 0
        errors = []

        # =========================
        # PROCESS ROWS
        # =========================
        for index, row in df.iterrows():
            row_dict = row.dropna().to_dict()

            try:
                data = map_excel_row_to_record(table, row_dict)

                validate_record_data(table, data)

                record = Record(
                    table_id=table.id,
                    data=data
                )

                db.session.add(record)
                inserted += 1

            except Exception as e:
                errors.append({
                    "row": index + 2,  # header + base 1
                    "error": str(e)
                })

        db.session.commit()

        # =========================
        # RESPONSE
        # =========================
        return {
            "inserted": inserted,
            "errors": errors
        }
