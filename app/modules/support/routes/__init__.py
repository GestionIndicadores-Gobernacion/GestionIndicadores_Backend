# app/modules/support/routes/__init__.py
from app.modules.support.routes.support_routes import blp as support_blp


def register_routes(api):
    api.register_blueprint(support_blp)
