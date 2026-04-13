from flask_smorest import Api

from app.modules.indicators.routes import register_indicators_routes
from app.modules.datasets.routes import register_routes as register_dataset_routes
from app.modules.action_plans.routes import register_routes as register_action_plan_routes
from app.modules.notifications.routes import register_routes as register_notification_routes


def _schema_name_resolver(schema):
    return schema.__class__.__module__ + "." + schema.__class__.__name__


def register_routes(app):
    """
    Crea la instancia Flask-Smorest Api y registra todos los blueprints.

    Recibe el Flask app ya configurado (con OPENAPI_* en app.config).
    Retorna la instancia Api por si se necesita en tests o extensiones.
    """
    api = Api(app, spec_kwargs={"schema_name_resolver": _schema_name_resolver})

    register_indicators_routes(api)
    register_dataset_routes(api)
    register_action_plan_routes(api)
    register_notification_routes(api)

    return api
