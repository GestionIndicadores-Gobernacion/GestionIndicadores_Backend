from flask import request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask_smorest import Blueprint, abort
from flask.views import MethodView

from domains.datasets.handlers.excel_import_handler import import_excel_dataset, update_excel_dataset
from domains.datasets.handlers.excel_preview_handler import preview_excel

blp = Blueprint(
    "dataset_import",
    __name__,
    url_prefix="/datasets"
)

def _is_admin():
    from domains.indicators.models.User.user import User
    verify_jwt_in_request()
    user = User.query.get(get_jwt_identity())
    return user and user.role and user.role.name == "admin"


@blp.route("/import-excel")
class DatasetImportResource(MethodView):

    def post(self):
        if not _is_admin():
            abort(403, message="Sin permiso")

        if "file" not in request.files:
            abort(400, message="Archivo Excel no enviado")

        file = request.files["file"]
        dataset_name = request.form.get("dataset_name") or file.filename.rsplit(".", 1)[0]

        return import_excel_dataset(file, dataset_name)


@blp.route("/import-excel/preview")
class DatasetImportPreviewResource(MethodView):

    def post(self):
        if not _is_admin():
            abort(403, message="Sin permiso")

        if "file" not in request.files:
            abort(400, message="Archivo Excel no enviado")

        file = request.files["file"]
        return {"preview": preview_excel(file)}


@blp.route("/<int:dataset_id>/update-excel")
class DatasetUpdateResource(MethodView):

    def put(self, dataset_id):
        if not _is_admin():
            abort(403, message="Sin permiso")

        if "file" not in request.files:
            abort(400, message="Archivo no enviado")

        file = request.files["file"]
        return update_excel_dataset(file, dataset_id)