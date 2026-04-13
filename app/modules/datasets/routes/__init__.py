import os
import importlib

def register_routes(api):
    base_module = "app.modules.datasets.routes"
    folder = os.path.dirname(__file__)

    for file in os.listdir(folder):
        if file.endswith("_routes.py") and not file.startswith("__"):
            module = importlib.import_module(f"{base_module}.{file[:-3]}")
            if hasattr(module, "blp"):
                api.register_blueprint(module.blp)

    # Dashboard (está en subcarpeta, no lo detecta el auto-discovery)
    from app.modules.datasets.dashboard.routes import blp as dashboard_blp
    api.register_blueprint(dashboard_blp)