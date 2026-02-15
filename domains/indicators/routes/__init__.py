import os
import importlib

def register_indicators_routes(api):
    route_folder = os.path.dirname(__file__)
    base_module = "domains.indicators.routes"

    for file in os.listdir(route_folder):
        if (
            file.endswith("_routes.py")
            and not file.startswith("__")
        ):
            module_name = f"{base_module}.{file[:-3]}"

            module = importlib.import_module(module_name)

            if hasattr(module, "blp"):
                api.register_blueprint(module.blp)
