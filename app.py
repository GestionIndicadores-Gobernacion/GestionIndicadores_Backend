from flask import Flask
from flask_migrate import Migrate
from flask_smorest import Api
from flask_jwt_extended import JWTManager
from config import Config
from db import db
from routes import register_routes

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_JSON_PATH"] = "api-spec.json"
    app.config["API_SPEC_OPTIONS"] = {"components": {"securitySchemes": {}}, "info": {"description": "Sistema indicador Gobernación"}}


    db.init_app(app)
    
    # 👇 IMPORTAR MODELOS AQUÍ
    from models.user import User
    from models.role import Role
    from models.permission import Permission
    from models.component import Component
    from models.indicator import Indicator
    from models.record import Record
    
    migrate = Migrate(app, db)

    jwt = JWTManager(app)
    
    api = Api(app)
    register_routes(api)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
