from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required
from flask import request

from domains.indicators.handlers.file_handler import FileHandler

blp = Blueprint(
    "files",
    "files",
    url_prefix="/files",
    description="File upload for indicators"
)


@blp.route("/upload")
class FileUploadResource(MethodView):

    @jwt_required()
    def post(self):
        """
        Sube un archivo al servidor y retorna sus metadatos.

        Form-data:
            - file: el archivo
            - report_id (opcional): para organizar en carpeta por reporte

        Response 201:
            {
                "file_name": "informe.pdf",
                "file_url": "https://tudominio.com/uploads/reports/42/abc123.pdf",
                "file_size_mb": 1.2,
                "mime_type": "application/pdf"
            }
        """
        file = request.files.get("file")
        report_id = request.form.get("report_id")

        result, errors = FileHandler.upload(file, report_id=report_id)

        if errors:
            return {"errors": errors}, 400

        return result, 201


@blp.route("/delete")
class FileDeleteResource(MethodView):

    @jwt_required()
    def delete(self):
        """
        Elimina un archivo del servidor dado su URL.

        JSON body:
            { "file_url": "https://tudominio.com/uploads/reports/42/abc123.pdf" }
        """
        data = request.get_json()

        if not data or not data.get("file_url"):
            return {"errors": {"file_url": "Required"}}, 400

        result, errors = FileHandler.delete_by_url(data["file_url"])

        if errors:
            return {"errors": errors}, 400

        return result, 200