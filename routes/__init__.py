import os
import importlib

def register_routes(api):
    route_folder = os.path.dirname(__file__)

    for file in os.listdir(route_folder):
        if file.endswith("_routes.py"):
            module_name = f"routes.{file[:-3]}"

            module = importlib.import_module(module_name)

            if hasattr(module, "blp"):
                api.register_blueprint(module.blp)
