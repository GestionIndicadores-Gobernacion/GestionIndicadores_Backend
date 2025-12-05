import os
from flask import Flask
from flask_migrate import Migrate
from flask_smorest import Api
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from config import Config
from extensions import db, bcrypt, jwt
from routes import register_routes
from sqlalchemy import inspect
from handlers.error_handlers import register_error_handlers


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ======================================================
    # 🔒 SSL SOLO EN PRODUCCIÓN (Render)
    # ======================================================
    if os.getenv("RENDER", False) or os.getenv("FLASK_ENV") == "production":
        print("🌐 Producción detectada → SSL ENABLED")
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"sslmode": "require"}
        }
    else:
        print("🖥️ Modo local → SSL DISABLED")
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {}

    print("JWT USADO:", app.config["JWT_SECRET_KEY"])

    # CORS
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    # OpenAPI
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_JSON_PATH"] = "api-spec.json"
    app.config["API_SPEC_OPTIONS"] = {
        "components": {"securitySchemes": {}},
        "info": {"description": "Sistema indicador Gobernación"}
    }

    # Inicializar extensiones
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    migrate = Migrate(app, db)

    # Importar modelos (necesario para Flask-Migrate)
    from models.user import User
    from models.role import Role
    from models.component import Component
    from models.indicator import Indicator
    from models.record import Record
    from models.activity import Activity

    # Comando seed manual
    from commands.seed import seed
    app.cli.add_command(seed)

    # Registrar rutas
    api = Api(app)
    register_routes(api)

    # Manejadores de error
    register_error_handlers(app)

    return app


def run_seed_if_needed(app):
    """Ejecuta el seed si la BD ya está creada y no hay roles."""
    with app.app_context():
        inspector = inspect(db.engine)

        if "roles" not in inspector.get_table_names():
            print("🚫 Tabla 'roles' no existe aún. Seed no ejecutado.")
            return

        from models.role import Role

        if Role.query.count() > 0:
            print("✔ Seed no necesario. Roles ya existen.")
            return

        print("⚙ Ejecutando seed automático…")
        from commands.seed import seed
        seed.main(standalone_mode=False)
        print("🎉 Seed ejecutado.")


# --------------------------------------------------------
# 📌 Render necesita esta variable "app"
# --------------------------------------------------------
app = create_app()

# Seed automático en Render
run_seed_if_needed(app)

# --------------------------------------------------------
# 📌 Modo local
# --------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
