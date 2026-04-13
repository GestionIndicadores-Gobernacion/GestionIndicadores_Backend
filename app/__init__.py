# Expone create_app desde el paquete para que FLASK_APP=app también funcione.
from app.main import create_app

__all__ = ["create_app"]
