import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuración base (desarrollo / producción)."""

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    API_TITLE = "API Sistema de Indicadores Gobernación"
    API_VERSION = "1.0.0"

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "cambia_esto_por_produccion")
    JWT_ACCESS_TOKEN_EXPIRES = 3600 * 8
    JWT_REFRESH_TOKEN_EXPIRES = 60 * 60 * 24 * 30

    JWT_ERROR_MESSAGE_KEY = "msg"
    JWT_IDENTITY_CLAIM = "sub"
    JWT_ENCODE_SUBJECT = True

    # 🔥 ESTA ES LA CLAVE
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"

    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", 10)) * 1024 * 1024
    BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")

    # Bandera usada por la factory para decidir comportamientos de entorno
    # (CORS, SSL, engine options). Solo `TestConfig` la pone en True.
    TESTING = False


class TestConfig(Config):
    """
    Config explícita para pytest. **NO lee `DATABASE_URL` del entorno** —
    fuerza SQLite en memoria de forma literal para que sea imposible que
    un test apunte por accidente a la BD de desarrollo / producción.
    """

    TESTING = True

    # SQLite en memoria, aislado por proceso. No se persiste nada.
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    # Options específicas de SQLite: no SSL y sin opciones de PostgreSQL
    # (evita que la factory inyecte `sslmode=require` accidentalmente).
    SQLALCHEMY_ENGINE_OPTIONS: dict = {}

    # Secret determinista para que los JWT creados en tests sean estables.
    JWT_SECRET_KEY = "test-secret-not-for-production"

    # Upload aislado en carpeta temporal del proceso.
    UPLOAD_FOLDER = "tests/_uploads_tmp"

    # Propagar excepciones para ver tracebacks reales en los tests.
    PROPAGATE_EXCEPTIONS = True