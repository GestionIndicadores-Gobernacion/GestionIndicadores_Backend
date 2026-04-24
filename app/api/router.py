from flask_smorest import Api

from app.modules.indicators.routes import register_indicators_routes
from app.modules.datasets.routes import register_routes as register_dataset_routes
from app.modules.action_plans.routes import register_routes as register_action_plan_routes
from app.modules.notifications.routes import register_routes as register_notification_routes


# Esquemas homónimos detectados entre módulos. Para estos, se antepone el
# namespace del módulo de dominio en la OpenAPI spec y así se eliminan los
# warnings "Multiple schemas resolved to the name X" al cargar la app.
_COLLIDING_SCHEMA_NAMES = {
    "User", "Dataset", "Field", "Record", "Table", "StrategyMetric",
}

_DOMAIN_PARTS = ("datasets", "action_plans", "notifications", "indicators", "shared")


def _schema_name_resolver(schema):
    cls = schema if isinstance(schema, type) else type(schema)
    name = cls.__name__
    # Quitamos el sufijo "Schema" para que el nombre expuesto coincida con
    # la intención del dominio (User en lugar de UserSchema).
    if name.endswith("Schema"):
        name = name[: -len("Schema")]
    if name not in _COLLIDING_SCHEMA_NAMES:
        return name
    # Si hay colisión, prefijar con el dominio al que pertenece.
    for part in cls.__module__.split("."):
        if part in _DOMAIN_PARTS:
            return f"{part.capitalize()}{name}"
    return name


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
