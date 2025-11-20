from flask import request
from flask_smorest import Blueprint, abort
from flask.views import MethodView
from db import db
from models.record import Record
from models.indicator import Indicator
from schemas.record_schema import RecordSchema
from utils.permissions import permission_required

blp = Blueprint("Records", "records", description="Gestión de registros/reportes")


@blp.route("/records")
class RecordList(MethodView):

    @permission_required('records.read')
    @blp.response(200, RecordSchema(many=True))
    def get(self):
        """Listar registros con filtros y paginación"""
        q = Record.query

        # Filtros opcionales
        municipio = request.args.get("municipio")
        if municipio:
            q = q.filter(Record.municipio.ilike(f"%{municipio}%"))

        component_id = request.args.get("component_id")
        if component_id:
            q = q.filter(Record.component_id == int(component_id))

        indicator_id = request.args.get("indicator_id")
        if indicator_id:
            q = q.filter(Record.indicator_id == int(indicator_id))

        tipo_poblacion = request.args.get("tipo_poblacion")
        if tipo_poblacion:
            q = q.filter(Record.tipo_poblacion.ilike(f"%{tipo_poblacion}%"))

        fecha_from = request.args.get("fecha_from")
        fecha_to = request.args.get("fecha_to")
        if fecha_from:
            q = q.filter(Record.fecha >= fecha_from)
        if fecha_to:
            q = q.filter(Record.fecha <= fecha_to)

        # 🔥 Paginación (default 20 por página)
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("limit", 20))

        result = q.order_by(Record.fecha.desc()).paginate(page=page, per_page=per_page, error_out=False)

        return result.items


    @blp.arguments(RecordSchema)
    @blp.response(201, RecordSchema)
    @blp.arguments(RecordSchema)
    @blp.response(201, RecordSchema)
    def post(self, new_record):
            # Validación: detalle_poblacion coincide con lista permitida cuando use_list=True
        if new_record.indicator_id:
            indicator = Indicator.query.get(new_record.indicator_id)

            if indicator.use_list and indicator.allowed_values:
                if new_record.detalle_poblacion:
                    invalid_keys = [
                        k for k in new_record.detalle_poblacion.keys()
                        if k not in indicator.allowed_values
                    ]
                    if invalid_keys:
                        abort(
                            400,
                            message=f"Valores inválidos en 'detalle_poblacion': {invalid_keys}. "
                                    f"Permitidos: {indicator.allowed_values}"
                        )



@blp.route("/records/<int:id>")
class RecordById(MethodView):

    @blp.response(200, RecordSchema)
    def get(self, id):
        r = Record.query.get(id)
        if not r:
            abort(404, message="Registro no encontrado.")
        return r

    def delete(self, id):
        r = Record.query.get(id)
        if not r:
            abort(404, message="Registro no existe.")
        db.session.delete(r)
        db.session.commit()
        return {"message": "Registro eliminado."}
