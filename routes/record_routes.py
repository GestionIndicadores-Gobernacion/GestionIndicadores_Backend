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
    def post(self, record):
        """
        Aquí record YA ES una instancia de Record,
        porque load_instance=True en RecordSchema.
        """
        try:
            validate_record_payload(record)  # sigue funcionando
            db.session.add(record)
            db.session.commit()
            return record

        except Exception as e:
            print("🔥 ERROR NO CONTROLADO:", type(e), e)
            db.session.rollback()
            raise e


@blp.route("/record/<int:id>")
class RecordDetail(MethodView):

    @jwt_required()
    @blp.response(200, RecordSchema)
    def get(self, id):
        return Record.query.get_or_404(id)

    @jwt_required()
    @blp.arguments(RecordSchema)
    @blp.response(200, RecordSchema)
    def put(self, new_record, id):
        """
        new_record también es una instancia de Record.
        Se copian los valores al existente.
        """
        existing = Record.query.get_or_404(id)

        validate_record_payload(new_record)

        # Lista de campos editables
        fields_to_copy = [
            "strategy_id",
            "component_id",
            "fecha",
            "detalle_poblacion",
            "evidencia_url",
        ]

        for field in fields_to_copy:
            setattr(existing, field, getattr(new_record, field))

        db.session.commit()
        return existing

    @jwt_required()
    def delete(self, id):
        record = Record.query.get_or_404(id)
        db.session.delete(record)
        db.session.commit()
        return {"message": "Registro eliminado correctamente"}


# ============================================================
# 📊 STATS: Registros por municipio (desde JSON)
# ============================================================
@blp.route("/record/stats/municipios")
class RecordStatsMunicipios(MethodView):

    @jwt_required()
    def get(self):
        registros = Record.query.with_entities(Record.detalle_poblacion).all()
        conteo = {}

        for (detalle,) in registros:
            if detalle and "municipios" in detalle:
                for municipio in detalle["municipios"].keys():
                    conteo[municipio] = conteo.get(municipio, 0) + 1

        return [
            {"municipio": m, "total": t}
            for m, t in sorted(conteo.items(), key=lambda x: x[1], reverse=True)
        ]


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

        from datetime import datetime
        today = datetime.utcnow()
        year = today.year
        month = today.month

        registros_mes = Record.query.filter(
            func.extract('year', Record.fecha) == year,
            func.extract('month', Record.fecha) == month
        ).count()

        registros = Record.query.with_entities(Record.detalle_poblacion).all()
        municipios = set()

        for (detalle,) in registros:
            if detalle and "municipios" in detalle:
                municipios.update(detalle["municipios"].keys())

        municipios_activos = len(municipios)

        indicadores = set()

        for (detalle,) in registros:
            if detalle and "municipios" in detalle:
                for info in detalle["municipios"].values():
                    if "indicadores" in info:
                        indicadores.update(info["indicadores"].keys())

        indicadores_activos = len(indicadores)

        componentes_activos = db.session.query(Record.component_id).distinct().count()

        return {
            "totalRegistros": total_registros,
            "registrosMes": registros_mes,
            "municipiosActivos": municipios_activos,
            "indicadoresActivos": indicadores_activos,
            "componentesActivos": componentes_activos
        }


# ============================================================
# 📊 Registros por estrategia
# ============================================================
@blp.route("/record/stats/estrategias")
class RecordStatsEstrategias(MethodView):

    @jwt_required()
    def get(self):
        results = (
            db.session.query(
                Record.strategy_id,
                func.count(Record.id).label("total")
            )
            .group_by(Record.strategy_id)
            .all()
        )

        from models.strategy import Strategy

        data = []
        for strategy_id, total in results:
            strategy = Strategy.query.get(strategy_id)
            if strategy:
                data.append({
                    "estrategia": strategy.name,
                    "total": total
                })

        return data


# ============================================================
# 📊 Registros por componente filtrados por estrategia
# ============================================================
@blp.route("/record/stats/componentes")
class RecordStatsComponentes(MethodView):

    @jwt_required()
    def get(self):
        estrategia_id = request.args.get("estrategia_id", type=int)

        query = db.session.query(
            Record.component_id,
            func.count(Record.id).label("total")
        )

        if estrategia_id:
            query = query.filter(Record.strategy_id == estrategia_id)

        results = (
            query.group_by(Record.component_id)
                 .order_by(func.count(Record.id).desc())
                 .all()
        )

        return [
            {
                "component_id": r[0],
                "total": r[1]
            }
            for r in results
        ]

# ============================================================
# 📊 Indicadores distintos por estrategia
# ============================================================
@blp.route("/record/stats/indicadores_por_estrategia")
class RecordStatsIndicadoresEstrategia(MethodView):

    @jwt_required()
    def get(self):
        from models.strategy import Strategy

        estrategias = Strategy.query.all()
        registros = Record.query.all()

        result = []

        for estr in estrategias:
            indicadores_set = set()

            for r in registros:
                if r.strategy_id != estr.id:
                    continue

                municipios = r.detalle_poblacion.get("municipios", {})
                for muni in municipios.values():
                    for ind_name in muni.get("indicadores", {}):
                        indicadores_set.add(ind_name)

            result.append({
                "estrategia": estr.name,
                "total_indicadores": len(indicadores_set)
            })

        return result
