# Dependencias de autenticación reutilizables en rutas.
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

__all__ = ["jwt_required", "get_jwt_identity", "get_jwt"]
