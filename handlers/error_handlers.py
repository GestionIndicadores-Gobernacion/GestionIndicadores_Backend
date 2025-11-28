from flask import jsonify
from marshmallow import ValidationError
from werkzeug.exceptions import NotFound, Unauthorized, Forbidden, BadRequest


def register_error_handlers(app):

    # =============================
    # 🟡 VALIDACIÓN (Marshmallow)
    # =============================
    @app.errorhandler(ValidationError)
    def handle_validation_error(err):
        return jsonify({
            "message": "Error de validación",
            "errors": err.messages
        }), 400

    # =============================
    # 🟡 404
    # =============================
    @app.errorhandler(NotFound)
    def handle_not_found(err):
        return jsonify({
            "message": "Recurso no encontrado",
        }), 404

    # =============================
    # 🟡 401
    # =============================
    @app.errorhandler(Unauthorized)
    def handle_unauthorized(err):
        return jsonify({
            "message": "No autorizado",
        }), 401

    # =============================
    # 🟡 403
    # =============================
    @app.errorhandler(Forbidden)
    def handle_forbidden(err):
        return jsonify({
            "message": "Acceso denegado",
        }), 403

    # =============================
    # 🟡 400
    # =============================
    @app.errorhandler(BadRequest)
    def handle_bad_request(err):
        return jsonify({
            "message": "Solicitud inválida",
        }), 400

    # =============================
    # 🟡 JWT — Errores estándar
    # =============================
    @app.errorhandler(Exception)
    def handle_generic_error(err):
        """
        Último handler: si es un error de JWT, Flask-JWT-Extended ya envía JSON.
        Si no, devolvemos un error 500 seguro.
        """
        from flask_jwt_extended.exceptions import JWTExtendedException
        if isinstance(err, JWTExtendedException):
            return jsonify({"message": str(err)}), 401

        print("🔥 ERROR NO CONTROLADO:", err)
        return jsonify({
            "message": "Error interno del servidor",
        }), 500
