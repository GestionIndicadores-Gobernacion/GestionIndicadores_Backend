import os
from flask import Flask, request
from flask_migrate import Migrate
from flask_cors import CORS

from app.core.config import Config
from app.core.extensions import db, bcrypt, jwt, ma
from app.api.router import register_routes
from app.modules.indicators.services.error_handlers import register_error_handlers
from app.modules.indicators.routes.public_policy_routes import seed_public_policies_command


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ======================================================
    # FIX CRÍTICO — PERMITIR AUTH HEADER A JWT
    # ======================================================
    @app.before_request
    def force_authorization_header():
        auth = request.headers.get("Authorization")
        if auth:
            request.environ["HTTP_AUTHORIZATION"] = auth

    # ======================================================
    # Evitar redirects por slash (/strategies vs /strategies/)
    # ======================================================
    app.url_map.strict_slashes = False

    # ======================================================
    # SSL SOLO EN PRODUCCIÓN
    # ======================================================
    if os.getenv("RENDER") or os.getenv("FLASK_ENV") == "production":
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"sslmode": "require"}
        }
    else:
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}

    # ======================================================
    # CORS
    # ======================================================
    CORS(
        app,
        resources={r"/*": {"origins": [
            "http://localhost:4200",
            "https://gestionindicadoresgov.netlify.app",
        ]}},
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        supports_credentials=True,
    )

    # ======================================================
    # OpenAPI — configuración consumida por Flask-Smorest
    # ======================================================
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_JSON_PATH"] = "api-spec.json"

    app.config["API_SPEC_OPTIONS"] = {
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            }
        },
        "security": [{"bearerAuth": []}],
        "info": {"description": "Sistema de Indicadores PYBA - Gobernación"},
    }

    # ======================================================
    # Inicializar extensiones
    # ======================================================
    db.init_app(app)
    ma.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    Migrate(app, db)

    # ======================================================
    # Importar modelos (registra tablas con SQLAlchemy)
    # ======================================================
    from app.modules.indicators import models   # noqa: F401
    from app.modules.datasets import models     # noqa: F401
    from app.modules.action_plans import models # noqa: F401
    from app.modules.notifications import models# noqa: F401

    # ======================================================
    # CLI — Seed commands
    # ======================================================
    from app.modules.indicators import commands
    app.cli.add_command(commands.seed)
    app.cli.add_command(commands.seed_users)
    app.cli.add_command(seed_public_policies_command)

    # ======================================================
    # Rutas — crea la instancia Api y registra blueprints
    # ======================================================
    register_routes(app)

    # ======================================================
    # Error handlers
    # ======================================================
    register_error_handlers(app)

    return app
