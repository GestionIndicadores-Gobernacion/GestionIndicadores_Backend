import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    API_TITLE = "API Sistema de Indicadores Gobernación"
    API_VERSION = "1.0.0"

    # JWT
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "cambia_esto_por_produccion")
    JWT_ACCESS_TOKEN_EXPIRES = 3600  # 1 hora (segundos)
    JWT_REFRESH_TOKEN_EXPIRES = 60 * 60 * 24 * 30  # 30 días
