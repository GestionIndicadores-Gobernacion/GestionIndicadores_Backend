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
    # Ventana de sesión absoluta de 24 h desde el login. Ambos tokens duran
    # lo mismo; `/auth/refresh` hereda el `exp` del refresh entrante (ver
    # `auth_routes.py`) para que un refresh no extienda la ventana.
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 24
    JWT_REFRESH_TOKEN_EXPIRES = 60 * 60 * 24

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

    # ── RBAC Bloque 12: shadow mode ─────────────────────────────────────
    # Cuando True, `dual_required` compara la decisión por rol (legacy
    # autoritativa) con la decisión por permisos (sombra) y loguea cada
    # divergencia. Default: False en producción para evitar ruido en logs.
    # Activar en staging (`PERM_SHADOW_MODE=true` en env) para validar
    # paridad antes de promover el sistema permisos como autoritativo.
    PERM_SHADOW_MODE = os.getenv("PERM_SHADOW_MODE", "false").lower() == "true"

    # ── Email de soporte (botón flotante de reporte de fallos) ──────────
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SUPPORT_EMAIL_TO = os.getenv("SUPPORT_EMAIL_TO", "juamcamirodri@gmail.com")
    SUPPORT_EMAIL_FROM_NAME = os.getenv("SUPPORT_EMAIL_FROM_NAME", "Indicadores PYBA — Soporte")


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

    # Rate limiter deshabilitado en tests — el endpoint /auth/login tiene
    # `8/min; 30/hour` y la suite hace decenas de logins. Sin esto, los
    # tests posteriores caen con 429.
    RATELIMIT_ENABLED = False