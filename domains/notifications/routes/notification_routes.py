# domains/notifications/routes/notification_routes.py
from flask import jsonify, request
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity

from domains.notifications.handlers.notification_handler import NotificationHandler
from domains.notifications.schemas.notification_schema import NotificationSchema

blp = Blueprint(
    "notifications", __name__,
    url_prefix="/notifications",
    description="Notificaciones del usuario"
)


@blp.route("/")
class NotificationList(MethodView):

    @jwt_required()
    def get(self):
        user_id = int(get_jwt_identity())
        unread_only = request.args.get("unread", "false").lower() == "true"

        # ── Generar recordatorios automáticos antes de devolver la lista ──
        try:
            NotificationHandler.generate_activity_reminders(user_id)
        except Exception:
            pass  # No romper la respuesta si algo falla

        notifications = NotificationHandler.get_by_user(user_id, unread_only=unread_only)
        return jsonify(NotificationSchema(many=True).dump(notifications)), 200

@blp.route("/count")
class NotificationCount(MethodView):

    @jwt_required()
    def get(self):
        user_id = int(get_jwt_identity())
        count = NotificationHandler.count_unread(user_id)
        return jsonify({"unread_count": count}), 200


@blp.route("/<int:notification_id>/read")
class NotificationMarkRead(MethodView):

    @jwt_required()
    def put(self, notification_id):
        user_id = int(get_jwt_identity())
        notification, errors = NotificationHandler.mark_as_read(notification_id, user_id)
        if errors:
            return jsonify({"errors": errors}), 404
        return jsonify(NotificationSchema().dump(notification)), 200


@blp.route("/read-all")
class NotificationMarkAllRead(MethodView):

    @jwt_required()
    def put(self):
        user_id = int(get_jwt_identity())
        count = NotificationHandler.mark_all_as_read(user_id)
        return jsonify({"marked": count}), 200