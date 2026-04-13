# app/modules/notifications/routes/__init__.py
from app.modules.notifications.routes.notification_routes import blp as notifications_blp


def register_routes(api):
    api.register_blueprint(notifications_blp)