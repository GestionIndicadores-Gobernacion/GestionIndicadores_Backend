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

    print("JWT USADO:", app.config["JWT_SECRET_KEY"])
    
    # CORS
    CORS(app, resources={r"/*": {"origins": "http://localhost:4200"}}, supports_credentials=True)

    # OpenAPI setup...
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_JSON_PATH"] = "api-spec.json"
    app.config["API_SPEC_OPTIONS"] = {
        "components": {"securitySchemes": {}},
        "info": {"description": "Sistema indicador Gobernación"}
    }

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    migrate = Migrate(app, db)

    # Importar modelos para Migrate
    from models.user import User
    from models.role import Role
    from models.component import Component
    from models.indicator import Indicator
    from models.record import Record

    # Seed
    from commands.seed import seed
    app.cli.add_command(seed)

    # 🔥 Registrar rutas
    api = Api(app)
    register_routes(api)

    # 🔥 Registrar HANDLERS GLOBALES
    register_error_handlers(app)

    return app

def run_seed_if_needed(app):
    """Ejecuta seed si las tablas ya están creadas y no hay roles."""
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


if __name__ == "__main__":
    app = create_app()
    run_seed_if_needed(app)
    app.run(debug=True)
