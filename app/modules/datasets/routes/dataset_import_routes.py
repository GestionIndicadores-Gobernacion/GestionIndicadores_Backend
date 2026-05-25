from flask import request
from flask_jwt_extended import jwt_required
from flask_smorest import Blueprint, abort
from flask.views import MethodView

from app.modules.datasets.services.excel_import_handler import import_excel_dataset, update_excel_dataset
from app.modules.datasets.services.excel_preview_handler import preview_excel
from app.utils.permissions import dual_required
from app.shared.permissions import PERM_DATASETS_IMPORT

blp = Blueprint(
    "dataset_import",
    __name__,
    url_prefix="/datasets"
)


@blp.route("/import-excel")
class DatasetImportResource(MethodView):

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_DATASETS_IMPORT,))
    def post(self):
        if "file" not in request.files:
            abort(400, message="Archivo Excel no enviado")

        file = request.files["file"]
        dataset_name = request.form.get("dataset_name") or file.filename.rsplit(".", 1)[0]

        return import_excel_dataset(file, dataset_name)


@blp.route("/import-excel/preview")
class DatasetImportPreviewResource(MethodView):

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_DATASETS_IMPORT,))
    def post(self):
        if "file" not in request.files:
            abort(400, message="Archivo Excel no enviado")

        file = request.files["file"]
        return {"preview": preview_excel(file)}


@blp.route("/<int:dataset_id>/update-excel")
class DatasetUpdateResource(MethodView):

    @jwt_required()
    @dual_required(roles=("admin",), perms=(PERM_DATASETS_IMPORT,))
    def put(self, dataset_id):
        file = request.files.get("file")
        dataset_name = request.form.get("dataset_name")

        if file is None and not (dataset_name and dataset_name.strip()):
            abort(400, message="Debe enviar un archivo o un nuevo nombre")

        return update_excel_dataset(file, dataset_id, dataset_name)