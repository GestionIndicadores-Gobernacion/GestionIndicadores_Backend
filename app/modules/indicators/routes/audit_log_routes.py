from flask import jsonify, request
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required

from app.shared.models.audit_log import AuditLog, AUDIT_LOG_RETENTION_DAYS
from app.shared.schemas.audit_log_schema import AuditLogSchema
from app.utils.permissions import role_required

blp = Blueprint(
    "audit_logs", "audit_logs",
    url_prefix="/audit-logs",
    description="Historial de acciones"
)


@blp.route("/")
class AuditLogList(MethodView):

    @jwt_required()
    @role_required("admin")           # solo admin puede ver el historial completo
    @blp.response(200, AuditLogSchema(many=True))
    def get(self):
        # Purga automática: borra registros más antiguos que el período de retención
        AuditLog.purge_old(AUDIT_LOG_RETENTION_DAYS)

        entity    = request.args.get("entity")
        entity_id = request.args.get("entity_id", type=int)
        user_id   = request.args.get("user_id",   type=int)

        query = AuditLog.query.order_by(AuditLog.created_at.desc())

        if entity:
            query = query.filter_by(entity=entity)
        if entity_id:
            query = query.filter_by(entity_id=entity_id)
        if user_id:
            query = query.filter_by(user_id=user_id)

        return query.all()


@blp.route("/purge")
class AuditLogPurge(MethodView):

    @jwt_required()
    @role_required("admin")
    def delete(self):
        """Purga manual: elimina registros más antiguos que el período de retención."""
        deleted = AuditLog.purge_old(AUDIT_LOG_RETENTION_DAYS)
        return jsonify({"deleted": deleted, "retention_days": AUDIT_LOG_RETENTION_DAYS})