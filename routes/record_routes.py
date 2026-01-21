from flask import request
from flask_smorest import Blueprint
from flask.views import MethodView
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from extensions import db

from models.record import Record
from schemas.record_schema import RecordSchema
from validators.record_validator import validate_record_payload

from utils.municipios_coord import MUNICIPIOS_COORD
from models.indicator import Indicator
from models.component import Component
from models.strategy import Strategy

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

        # 🔥 DERIVAR DESDE COMPONENTE
        validate_record_payload(record)

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
    def put(self, new_record, id):
        """
        PUT completo:
        - frontend manda component_id
        - backend recalcula activity_id y strategy_id
        """
        existing = Record.query.get_or_404(id)

        validate_record_payload(new_record)

        fields_to_copy = [
        "component_id",
        "fecha",
        "description",
        "actividades_realizadas",
        "detalle_poblacion",
        "evidencia_url",
        ]

        for field in fields_to_copy:
            setattr(existing, field, getattr(new_record, field))

        # 🔥 DERIVAR NUEVAMENTE
        validate_record_payload(existing)

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
# 📅 STATS: Registros por mes
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

        return (
            Record.query
            .order_by(Record.fecha_registro.desc())
            .limit(limit)
            .all()
        )


# ============================================================
# 📊 KPIs Dashboard
# ============================================================
@blp.route("/record/stats/count")
class RecordStatsCount(MethodView):

    @jwt_required()
    def get(self):
        total_registros = Record.query.count()

        from datetime import datetime
        today = datetime.utcnow()

        registros_mes = Record.query.filter(
            func.extract('year', Record.fecha) == today.year,
            func.extract('month', Record.fecha) == today.month
        ).count()

        registros = Record.query.with_entities(Record.detalle_poblacion).all()

        municipios = set()
        indicadores = set()

        for (detalle,) in registros:
            if detalle and "municipios" in detalle:
                for info in detalle["municipios"].values():
                    municipios.add(info)
                    indicadores.update(info.get("indicadores", {}).keys())

        componentes_activos = (
            db.session.query(Record.component_id).distinct().count()
        )

        return {
            "totalRegistros": total_registros,
            "registrosMes": registros_mes,
            "municipiosActivos": len(municipios),
            "indicadoresActivos": len(indicadores),
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
# 📊 Registros por componente
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

        return [{"component_id": r[0], "total": r[1]} for r in results]


# ============================================================
# 📊 Avance de indicadores
# ============================================================
@blp.route("/record/stats/avance_indicadores")
class RecordStatsAvanceIndicadores(MethodView):

    @jwt_required()
    def get(self):
        year = request.args.get("year", type=int)
        estrategia_id = request.args.get("estrategia_id", type=int)
        component_id = request.args.get("component_id", type=int)

        query = Record.query

        if year:
            query = query.filter(func.extract('year', Record.fecha) == year)
        if estrategia_id:
            query = query.filter(Record.strategy_id == estrategia_id)
        if component_id:
            query = query.filter(Record.component_id == component_id)

        registros = query.all()
        indicadores = (
            Indicator.query.filter_by(component_id=component_id).all()
            if component_id else Indicator.query.all()
        )

        data_final = []

        for ind in indicadores:
            acumulado_mes = {}
            acumulado_municipios = {}

            for r in registros:
                if r.component_id != ind.component_id:
                    continue

                mes = r.fecha.strftime("%Y-%m")
                municipios = r.detalle_poblacion.get("municipios", {})

                for muni, info in municipios.items():
                    valor = info.get("indicadores", {}).get(ind.name)
                    if valor is None:
                        continue

                    acumulado_mes[mes] = acumulado_mes.get(mes, 0) + valor
                    acumulado_municipios[muni] = acumulado_municipios.get(muni, 0) + valor

            if not acumulado_mes:
                continue

            componente = Component.query.get(ind.component_id)
            estrategia = Strategy.query.get(componente.strategy_id)

            data_final.append({
                "estrategia": estrategia.name,
                "component_id": ind.component_id,
                "indicador_id": ind.id,
                "indicador": ind.name,
                "meta": ind.meta,
                "meses": [
                    {
                        "mes": m,
                        "valor": v,
                        "avance": round((v / ind.meta) * 100, 2) if ind.meta else 0
                    }
                    for m, v in sorted(acumulado_mes.items())
                ],
                "municipios": [
                    {"municipio": m, "valor": v}
                    for m, v in sorted(acumulado_municipios.items())
                ]
            })

        return data_final


# ============================================================
# 📊 EXPORT POWER BI
# ============================================================
@blp.route("/record/powerbi")
class RecordPowerBI(MethodView):

    def get(self):
        registros = Record.query.all()
        data = []

        for r in registros:
            estrategia = Strategy.query.get(r.strategy_id)
            componente = Component.query.get(r.component_id)

            municipios = r.detalle_poblacion.get("municipios", {})

            for municipio, info in municipios.items():
                lat, lng = MUNICIPIOS_COORD.get(municipio, (None, None))

                for ind_name, valor in info.get("indicadores", {}).items():
                    indicador = Indicator.query.filter_by(name=ind_name).first()
                    meta = indicador.meta if indicador else 0
                    avance = (valor / meta * 100) if meta else 0

                    data.append({
                        "record_id": r.id,
                        "fecha": r.fecha.strftime("%Y-%m-%d"),
                        "municipio": municipio,
                        "lat": lat,
                        "lng": lng,
                        "indicador": ind_name,
                        "valor": valor,
                        "meta": meta,
                        "avance": round(avance, 2),
                        "estrategia": estrategia.name if estrategia else None,
                        "componente": componente.name if componente else None,
                    })

        return data


# ============================================================
# 📅 Años disponibles
# ============================================================
@blp.route("/record/years")
class RecordYears(MethodView):

    @jwt_required()
    def get(self):
        years = (
            db.session.query(func.extract('year', Record.fecha))
            .distinct()
            .order_by("year")
            .all()
        )

        return [int(y[0]) for y in years]
