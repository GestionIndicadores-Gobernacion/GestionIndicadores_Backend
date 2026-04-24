import logging
import os

from flask import jsonify, request
from sqlalchemy.exc import SQLAlchemyError
from app.core.extensions import db, jwt


def register_error_handlers(app):
    logger = logging.getLogger("app.errors")

    # ==================================================================
    # JWT — respuestas consistentes para que el frontend pueda distinguir
    # expirado / inválido / ausente y reaccionar correctamente.
    # Todos los casos devuelven 401 con un campo `error` estable.
    # ==================================================================
    @jwt.expired_token_loader
    def _jwt_expired(jwt_header, jwt_payload):
        token_type = jwt_payload.get("type", "access")
        return jsonify({
            "error": "token_expired",
            "token_type": token_type,
            "msg": "El token ha expirado."
        }), 401

    @jwt.invalid_token_loader
    def _jwt_invalid(reason):
        return jsonify({
            "error": "token_invalid",
            "msg": "El token es inválido."
        }), 401

    @jwt.unauthorized_loader
    def _jwt_missing(reason):
        return jsonify({
            "error": "token_missing",
            "msg": "No se ha enviado un token de autenticación."
        }), 401

    @jwt.revoked_token_loader
    def _jwt_revoked(jwt_header, jwt_payload):
        return jsonify({
            "error": "token_revoked",
            "msg": "El token ha sido revocado."
        }), 401

    @jwt.needs_fresh_token_loader
    def _jwt_needs_fresh(jwt_header, jwt_payload):
        return jsonify({
            "error": "fresh_token_required",
            "msg": "Se requiere un token fresco."
        }), 401

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(e):
        db.session.rollback()
        logger.exception(
            "DB error on %s %s", request.method, request.path
        )

        msg = str(e).lower()

        if "value too long" in msg:
            message = "El valor ingresado es demasiado largo."
        elif "duplicate key value" in msg:
            message = "Ya existe un registro con ese valor."
        elif "not-null constraint" in msg:
            message = "Hay campos obligatorios sin completar."
        else:
            message = "Ocurrió un error al guardar la información."

        return jsonify({
            "message": message
        }), 400


    @app.errorhandler(Exception)
    def handle_generic_error(e):
        # No interferir con respuestas HTTP estructuradas (JWT, smorest, etc.)
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e

        # Log completo con traceback para diagnóstico; nunca se devuelve al cliente.
        logger.exception(
            "Unhandled error on %s %s", request.method, request.path
        )

        body = {"message": "Ocurrió un error interno en el servidor."}
        # En dev, añadir el detalle para acelerar debugging. Jamás en prod.
        is_dev = (
            os.getenv("FLASK_ENV", "development") != "production"
            and not os.getenv("RENDER")
        )
        if is_dev:
            body["debug"] = f"{type(e).__name__}: {e}"
        return jsonify(body), 500