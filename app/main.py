import os
import re
from flask import Flask, request, make_response
from flask_migrate import Migrate
from flask_cors import CORS

from app.core.config import Config
from app.core.extensions import db, bcrypt, jwt, ma, limiter
from app.api.router import register_routes
from app.modules.indicators.services.error_handlers import register_error_handlers
from app.modules.indicators.routes.public_policy_routes import seed_public_policies_command


# ======================================================
# CORS — orígenes permitidos
# ======================================================
ALLOWED_ORIGINS = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
    "https://gestionindicadoresgov.netlify.app",
]

# Acepta también deploy previews de Netlify: https://<hash>--<site>.netlify.app
NETLIFY_PREVIEW_RE = re.compile(
    r"^https://[a-z0-9-]+--gestionindicadoresgov\.netlify\.app$",
    re.IGNORECASE,
)

ALLOWED_HEADERS = "Content-Type, Authorization, Accept, X-Requested-With"
ALLOWED_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"


def _is_origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    if origin in ALLOWED_ORIGINS:
        return True
    if NETLIFY_PREVIEW_RE.match(origin):
        return True
    return False


def create_app(config_class=Config):
    """
    Flask application factory.

    :param config_class: Clase de configuración a usar. Por defecto usa
        `Config` (dev/prod, lee .env). Para tests, pasar `TestConfig`
        desde el conftest — así NO se toca `os.environ` globalmente y es
        imposible que un test apunte por accidente a la BD de desarrollo.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ======================================================
    # FIX CRÍTICO — PERMITIR AUTH HEADER A JWT
    # ======================================================
    @app.before_request
    def force_authorization_header():
        auth = request.headers.get("Authorization")
        if auth:
            request.environ["HTTP_AUTHORIZATION"] = auth

    # ======================================================
    # CORS preflight — short-circuit ANTES del routing
    #
    # Algunas rutas tienen `decorators = [jwt_required()]` a nivel de
    # MethodView, y algunos proxies (Cloudflare/Render) pueden reescribir
    # la respuesta OPTIONS. Respondemos el preflight aquí mismo con 204
    # para garantizar que el navegador siempre lo vea como OK.
    # ======================================================
    @app.before_request
    def handle_cors_preflight():
        if request.method != "OPTIONS":
            return None
        origin = request.headers.get("Origin", "")
        if not _is_origin_allowed(origin):
            return None  # deja que el flujo normal lo rechace

        resp = make_response("", 204)
        req_headers = request.headers.get("Access-Control-Request-Headers", ALLOWED_HEADERS)
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Methods"] = ALLOWED_METHODS
        resp.headers["Access-Control-Allow-Headers"] = req_headers
        resp.headers["Access-Control-Max-Age"] = "86400"
        resp.headers["Vary"] = "Origin"
        return resp

    # ======================================================
    # Asegurar headers CORS en TODAS las respuestas (incluso 4xx/5xx)
    # Flask-CORS lo hace, pero si por alguna razón no se aplican (errores
    # tempranos, handlers custom), este after_request lo garantiza.
    # ======================================================
    @app.after_request
    def ensure_cors_headers(response):
        origin = request.headers.get("Origin", "")
        if _is_origin_allowed(origin):
            # No sobreescribir si ya fueron añadidos correctamente.
            response.headers.setdefault("Access-Control-Allow-Origin", origin)
            response.headers.setdefault("Access-Control-Allow-Credentials", "true")
            response.headers.setdefault("Vary", "Origin")
        return response

    # ======================================================
    # Evitar redirects por slash (/strategies vs /strategies/)
    # ======================================================
    app.url_map.strict_slashes = False

    # ======================================================
    # SSL SOLO EN PRODUCCIÓN
    # TestConfig ya fija SQLALCHEMY_ENGINE_OPTIONS={} — si estamos en
    # modo TESTING no tocamos nada (SQLite no acepta sslmode).
    # ======================================================
    if not app.config.get("TESTING"):
        if os.getenv("RENDER") or os.getenv("FLASK_ENV") == "production":
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
                "connect_args": {"sslmode": "require"}
            }
        else:
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}

    # ======================================================
    # CORS — capa principal (Flask-CORS)
    # El before_request/after_request de arriba ya garantiza el preflight,
    # pero Flask-CORS sigue activado para responder con headers correctos
    # en las respuestas reales (no preflight) y manejar `expose_headers`.
    # ======================================================
    CORS(
        app,
        resources={r"/*": {"origins": ALLOWED_ORIGINS + [NETLIFY_PREVIEW_RE]}},
        allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
        expose_headers=["Content-Disposition"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        supports_credentials=True,
        max_age=86400,
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
    limiter.init_app(app)
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
    # CLI — Mantenimiento de audit logs
    # ======================================================
    import click
    from app.shared.models.audit_log import AuditLog, AUDIT_LOG_RETENTION_DAYS

    @app.cli.command("purge-audit-logs")
    @click.option("--days", default=AUDIT_LOG_RETENTION_DAYS, show_default=True,
                  help="Días de retención. Registros más antiguos serán eliminados.")
    def purge_audit_logs_cmd(days):
        """Elimina registros de auditoría más antiguos que el período de retención."""
        deleted = AuditLog.purge_old(days)
        click.echo(f"Purga completada: {deleted} registro(s) eliminado(s) (retención: {days} días).")

    # ======================================================
    # Rutas — crea la instancia Api y registra blueprints
    # ======================================================
    register_routes(app)

    # ======================================================
    # Error handlers
    # ======================================================
    register_error_handlers(app)

    return app
