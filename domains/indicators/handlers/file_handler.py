import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx",
    "png", "jpg", "jpeg", "gif",
    "txt", "csv", "zip"
}


class FileHandler:

    # =====================================================
    # UPLOAD
    # =====================================================
    @staticmethod
    def upload(file, report_id=None):
        """
        Guarda el archivo en disco y retorna sus metadatos.

        Args:
            file: werkzeug FileStorage (viene de request.files["file"])
            report_id: opcional, para organizar en subcarpeta por reporte

        Returns:
            (result, None) con result = dict de metadatos
            (None, errors) si algo falla
        """
        if not file or file.filename == "":
            return None, {"file": "No file provided"}

        if not FileHandler._allowed(file.filename):
            return None, {"file": "File type not allowed"}

        try:
            original_name = secure_filename(file.filename)
            extension = original_name.rsplit(".", 1)[1].lower()
            unique_name = f"{uuid.uuid4().hex}.{extension}"

            subfolder = f"reports/{report_id}" if report_id else "general"
            upload_folder = current_app.config["UPLOAD_FOLDER"]
            dest_folder = os.path.join(upload_folder, subfolder)
            os.makedirs(dest_folder, exist_ok=True)

            filepath = os.path.join(dest_folder, unique_name)
            file.save(filepath)

            size_mb = round(os.path.getsize(filepath) / (1024 * 1024), 2)
            base_url = current_app.config["BASE_URL"]
            file_url = f"{base_url}/uploads/{subfolder}/{unique_name}"

            return {
                "file_name": original_name,
                "file_url": file_url,
                "file_size_mb": size_mb,
                "mime_type": file.mimetype
            }, None

        except Exception as e:
            return None, {"database": str(e)}

    # =====================================================
    # DELETE
    # =====================================================
    @staticmethod
    def delete_by_url(file_url):
        """
        Elimina un archivo del disco dado su URL publica.
        """
        try:
            base_url = current_app.config["BASE_URL"]
            upload_folder = current_app.config["UPLOAD_FOLDER"]

            prefix = f"{base_url}/uploads/"
            if not file_url.startswith(prefix):
                return None, {"file": "Invalid file URL"}

            relative_path = file_url[len(prefix):]
            filepath = os.path.join(upload_folder, relative_path)

            if os.path.exists(filepath):
                os.remove(filepath)

            return {"deleted": True}, None

        except Exception as e:
            return None, {"database": str(e)}

    # =====================================================
    # PRIVATE
    # =====================================================
    @staticmethod
    def _allowed(filename):
        return (
            "." in filename
            and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
        )