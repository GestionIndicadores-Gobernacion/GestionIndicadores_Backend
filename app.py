import os
from flask import Flask
from flask_migrate import Migrate
from flask_smorest import Api
from flask_cors import CORS
from sqlalchemy import inspect

from config import Config
from extensions import db, bcrypt, jwt, ma
from domains.indicators.routes import register_indicators_routes
from domains.indicators.handlers.error_handlers import register_error_handlers
from domains.datasets.routes import register_routes as register_dataset_routes


def schema_name_resolver(schema):
        # Usa el nombre completo del módulo + clase
        return schema.__class__.__module__ + "." + schema.__class__.__name__
    
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ======================================================
    # 🚫 Evitar redirects por slash (/strategies vs /strategies/)
    # ======================================================
    app.url_map.strict_slashes = False

    # ======================================================
    # 🔒 SSL SOLO EN PRODUCCIÓN
    # ======================================================
    if os.getenv("RENDER") or os.getenv("FLASK_ENV") == "production":
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"sslmode": "require"}
        }
    else:
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}

    # ======================================================
    # 🌐 CORS
    # ======================================================
    CORS(
        app,
        resources={r"/*": {"origins": "http://localhost:4200"}},
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )

    # ======================================================
    # 📘 OpenAPI + JWT
    # ======================================================
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_JSON_PATH"] = "api-spec.json"

    app.config["API_SPEC_OPTIONS"] = {
        # 👇 ESTA LÍNEA ES LA CLAVE
        "schema_name_resolver": schema_name_resolver,

        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            }
        },
        "security": [{"bearerAuth": []}],
        "info": {
            "description": "Sistema de Indicadores PYBA - Gobernación"
        }
    }

    # ======================================================
    # 🔌 Inicializar extensiones
    # ======================================================
    db.init_app(app)
    ma.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    Migrate(app, db)

    # ======================================================
    # 📦 Importar modelos (Indicators)
    # ======================================================
    from domains.indicators import models
    
    # ======================================================
    # 📦 Importar modelos (Datasets)
    # ======================================================
    from domains.datasets import models


    # ======================================================
    # 🌱 Seed
    # ======================================================
    from domains.indicators import commands

    app.cli.add_command(commands.seed)
    app.cli.add_command(commands.seed_users)


    # ======================================================
    # 🚏 Rutas
    # ======================================================
    api = Api(
    app,
    spec_kwargs={
        "schema_name_resolver": schema_name_resolver
    }
)

    register_indicators_routes(api)
    register_dataset_routes(api)
    # print(app.url_map)

    # ======================================================
    # ❌ Error handlers
    # ======================================================
    register_error_handlers(app)

    return app


# --------------------------------------------------------
# 📌 Render necesita esta variable
# --------------------------------------------------------
app = create_app()


# --------------------------------------------------------
# 📌 Modo local
# --------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
