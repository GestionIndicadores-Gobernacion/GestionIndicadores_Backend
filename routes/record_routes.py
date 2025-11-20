from flask import request
from flask_smorest import Blueprint, abort
from flask.views import MethodView
from flask_jwt_extended import get_jwt_identity
from datetime import datetime

from extensions import db
from models.record import Record
from models.indicator import Indicator
from models.component import Component
from schemas.record_schema import RecordSchema
from utils.permissions import permission_required

blp = Blueprint("Records", "records", description="Gestión de registros/reportes")


# -------------------------------------------------------------
# FUNCIONES AUXILIARES DE VALIDACIÓN
# -------------------------------------------------------------
def validate_indicator_value(indicator, valor):
    """Valida el valor según el tipo del indicador."""
    if indicator.data_type == "integer":
        if not valor.isdigit():
            abort(400, message="El valor debe ser un entero.")

    elif indicator.data_type == "decimal":
        try:
            float(valor)
        except ValueError:
            abort(400, message="El valor debe ser un número decimal.")

    elif indicator.data_type == "boolean":
        if valor.lower() not in ["true", "false"]:
            abort(400, message="El valor debe ser true o false.")

    elif indicator.data_type == "date":
        try:
            datetime.strptime(valor, "%Y-%m-%d")
        except ValueError:
            abort(400, message="El valor debe ser una fecha válida (YYYY-MM-DD).")

    elif indicator.data_type == "category":
        if valor not in indicator.allowed_values:
            abort(
                400,
                message=f"Valor inválido. Permitidos: {indicator.allowed_values}"
            )


def validate_detalle_poblacion(indicator, detalle):
    """Valida el diccionario detalle_poblacion según allowed_values."""
    if indicator.use_list and indicator.allowed_values:
        invalid_keys = [k for k in detalle.keys() if k not in indicator.allowed_values]
        if invalid_keys:
            abort(
                400,
                message=(
                    f"Valores inválidos en detalle_poblacion: {invalid_keys}. "
                    f"Permitidos: {indicator.allowed_values}"
                )
            )

def normalize_tipo_poblacion(value):
    """Convierte tipo_poblacion en lista siempre."""
    if isinstance(value, str):
        return [value]

    if isinstance(value, list):
        return value

    abort(400, message="tipo_poblacion debe ser string o lista.")


# -------------------------------------------------------------
# LISTAR Y CREAR REGISTROS
# -------------------------------------------------------------
@blp.route("/records")
class RecordList(MethodView):

    @permission_required('records.read')
    @blp.response(200, RecordSchema(many=True))
    def get(self):
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
            q = q.filter(Record.tipo_poblacion.contains([tipo_poblacion]))

        fecha_from = request.args.get("fecha_from")
        fecha_to = request.args.get("fecha_to")

        if fecha_from:
            q = q.filter(Record.fecha >= fecha_from)
        if fecha_to:
            q = q.filter(Record.fecha <= fecha_to)

        return q.order_by(Record.fecha.desc()).all()


    @permission_required('records.create')
    @blp.arguments(RecordSchema)
    @blp.response(201, RecordSchema)
    def post(self, data):
        # data es un DICT (porque load_instance=False)

        indicator = Indicator.query.get(data["indicator_id"])

        if indicator is None:
            abort(400, message="El indicador no existe.")

        # Validar relación entre componente e indicador
        if indicator.component_id != data["component_id"]:
            abort(400, message="El indicador no pertenece al componente enviado.")

        # Validar valor
        if data.get("valor"):
            validate_indicator_value(indicator, data["valor"])

        # Validar detalle poblacional
        if data.get("detalle_poblacion"):
            validate_detalle_poblacion(indicator, data["detalle_poblacion"])
            
        # Normalizar tipo_poblacion
        data["tipo_poblacion"] = normalize_tipo_poblacion(data["tipo_poblacion"])

        # Obtener usuario desde token
        user_id = get_jwt_identity()

        # Crear modelo manualmente
        record = Record(
            component_id=data["component_id"],
            indicator_id=data["indicator_id"],
            municipio=data["municipio"],
            fecha=data["fecha"],
            tipo_poblacion=data["tipo_poblacion"],  # lista
            detalle_poblacion=data.get("detalle_poblacion"),
            valor=data.get("valor"),
            evidencia_url=data.get("evidencia_url"),
            creado_por=str(user_id),
        )

        db.session.add(record)
        db.session.commit()

        return record


# -------------------------------------------------------------
# CRUD POR ID
# -------------------------------------------------------------
@blp.route("/records/<int:id>")
class RecordById(MethodView):

    @permission_required('records.read')
    @blp.response(200, RecordSchema)
    def get(self, id):
        record = Record.query.get(id)
        if not record:
            abort(404, message="Registro no encontrado.")
        return record


    @permission_required('records.update')
    @blp.arguments(RecordSchema)
    @blp.response(200, RecordSchema)
    def put(self, data, id):
        record = Record.query.get(id)
        if not record:
            abort(404, message="Registro no existe.")

        indicator = Indicator.query.get(data["indicator_id"])
        if not indicator:
            abort(404, message="Indicador no existe.")

        if indicator.component_id != data["component_id"]:
            abort(400, message="El indicador no pertenece al componente enviado.")

        if data.get("valor"):
            validate_indicator_value(indicator, data["valor"])

        if data.get("detalle_poblacion"):
            validate_detalle_poblacion(indicator, data["detalle_poblacion"])
            
        data["tipo_poblacion"] = normalize_tipo_poblacion(data["tipo_poblacion"])

        # Actualizar
        record.component_id = data["component_id"]
        record.indicator_id = data["indicator_id"]
        record.municipio = data["municipio"]
        record.fecha = data["fecha"]
        record.tipo_poblacion = data["tipo_poblacion"]
        record.detalle_poblacion = data.get("detalle_poblacion")
        record.valor = data.get("valor")
        record.evidencia_url = data.get("evidencia_url")

        db.session.commit()
        return record


    @permission_required('records.delete')
    def delete(self, id):
        record = Record.query.get(id)
        if not record:
            abort(404, message="Registro no existe.")

        db.session.delete(record)
        db.session.commit()

        return {"message": "Registro eliminado."}
