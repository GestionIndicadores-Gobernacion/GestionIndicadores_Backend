from datetime import datetime
from app.core.extensions import db


class Permission(db.Model):
    """Catálogo de permisos del sistema RBAC.

    Las filas se mantienen sincronizadas con el catálogo definido en
    `app/shared/permissions/catalog.py` mediante el comando CLI
    `flask seed_permissions`. NO se crean desde la UI: el catálogo es
    parte del código fuente y evita que existan permisos huérfanos que
    ningún endpoint chequee.
    """
    __tablename__ = "permissions"

    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    module      = db.Column(db.String(50), nullable=False, index=True)
    is_system   = db.Column(db.Boolean, default=False, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Permission {self.code}>"
