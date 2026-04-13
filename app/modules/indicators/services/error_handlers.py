from flask import jsonify
from sqlalchemy.exc import SQLAlchemyError
from app.core.extensions import db


def register_error_handlers(app):

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(e):
        db.session.rollback()

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
        return jsonify({
            "message": "Ocurrió un error interno en el servidor."
        }), 500