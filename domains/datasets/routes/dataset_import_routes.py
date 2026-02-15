from flask import request
from flask_smorest import Blueprint, abort
from flask.views import MethodView

from domains.datasets.handlers.excel_import_handler import import_excel_dataset
from domains.datasets.handlers.excel_preview_handler import preview_excel

blp = Blueprint(
    "dataset_import",
    __name__,
    url_prefix="/datasets"
)


@blp.route("/import-excel")
class DatasetImportResource(MethodView):

    def post(self):
        if "file" not in request.files:
            abort(400, message="Archivo Excel no enviado")

        file = request.files["file"]
        dataset_name = request.form.get("dataset_name") or file.filename.rsplit(".", 1)[0]

        return import_excel_dataset(file, dataset_name)


@blp.route("/import-excel/preview")
class DatasetImportPreviewResource(MethodView):

    def post(self):
        if "file" not in request.files:
            abort(400, message="Archivo Excel no enviado")

        file = request.files["file"]
        return {
            "preview": preview_excel(file)
        }
