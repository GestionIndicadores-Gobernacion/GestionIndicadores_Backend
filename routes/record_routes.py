from flask import request
from flask_smorest import Blueprint
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from extensions import db
from models.record import Record
from schemas.record_schema import RecordSchema
from validators.record_validator import validate_record_payload

blp = Blueprint("record", "record", description="Gestión de registros")


# ============================================================
# 📌 CRUD PRINCIPAL
# ============================================================
@blp.route("/record")
class RecordList(MethodView):

    @jwt_required()
    @blp.response(200, RecordSchema(many=True))
    def get(self):
        return Record.query.all()

    @jwt_required()
    @blp.arguments(RecordSchema)
    @blp.response(201, RecordSchema)
    def post(self, data):
        validate_record_payload(data)
        record = data
        db.session.add(record)
        db.session.commit()
        return record


@blp.route("/record/<int:id>")
class RecordDetail(MethodView):

    @jwt_required()
    @blp.response(200, RecordSchema)
    def get(self, id):
        return Record.query.get_or_404(id)

    @jwt_required()
    @blp.arguments(RecordSchema)
    @blp.response(200, RecordSchema)
    def put(self, data, id):
        existing = Record.query.get_or_404(id)
        validate_record_payload(data)

        for key, value in data.__dict__.items():
            if key not in ["id", "_sa_instance_state"]:
                setattr(existing, key, value)

        db.session.commit()
        return existing

    @jwt_required()
    def delete(self, id):
        record = Record.query.get_or_404(id)
        db.session.delete(record)
        db.session.commit()
        return {"message": "Registro eliminado correctamente"}


# ============================================================
# 📊 STATS: Registros por municipio
# ============================================================
@blp.route("/record/stats/municipios")
class RecordStatsMunicipios(MethodView):

    @jwt_required()
    def get(self):
        results = (
            db.session.query(
                Record.municipio,
                func.count(Record.id).label("total")
            )
            .group_by(Record.municipio)
            .order_by(func.count(Record.id).desc())
            .all()
        )

        return [{"municipio": r[0], "total": r[1]} for r in results]


# ============================================================
# 📅 STATS: Registros por mes (YYYY-MM)
# ============================================================
@blp.route("/record/stats/mes")
class RecordStatsMes(MethodView):

    @jwt_required()
    def get(self):
        results = (
            db.session.query(
                func.to_char(Record.fecha, "YYYY-MM").label("mes"),
                func.count(Record.id).label("total")
            )
            .group_by("mes")
            .order_by("mes")
            .all()
        )

        return [{"mes": r[0], "total": r[1]} for r in results]


# ============================================================
# 🕒 Últimos registros
# ============================================================
@blp.route("/record/latest")
class RecordLatest(MethodView):

    @jwt_required()
    @blp.response(200, RecordSchema(many=True))
    def get(self):
        limit = int(request.args.get("limit", 5))

        records = (
            Record.query
            .order_by(Record.fecha_registro.desc())
            .limit(limit)
            .all()
        )

        return records


# ============================================================
# 📊 KPIs para el Dashboard
# ============================================================
@blp.route("/record/stats/count")
class RecordStatsCount(MethodView):

    @jwt_required()
    def get(self):
        total_registros = Record.query.count()

        # Registros del mes actual
        from datetime import datetime
        today = datetime.utcnow()
        year = today.year
        month = today.month

        registros_mes = Record.query.filter(
            func.extract('year', Record.fecha) == year,
            func.extract('month', Record.fecha) == month
        ).count()

        # Municipios distintos
        municipios_activos = db.session.query(Record.municipio).distinct().count()

        # indicadores activos (extraer IDs del JSON 'detalle_poblacion')
        registros = Record.query.with_entities(Record.detalle_poblacion).all()

        ids_indicadores = set()

        for (detalle,) in registros:
            if detalle:
                ids_indicadores.update(detalle.keys())

        indicadores_activos = len(ids_indicadores)


        # Componentes activos
        componentes_activos = db.session.query(Record.component_id).distinct().count()

        return {
            "totalRegistros": total_registros,
            "registrosMes": registros_mes,
            "municipiosActivos": municipios_activos,
            "indicadoresActivos": indicadores_activos,
            "componentesActivos": componentes_activos
        }
