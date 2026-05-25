from app.core.extensions import db

from datetime import datetime


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(50), unique=True, nullable=False)

    # ── RBAC: campos auxiliares para UI admin (Bloque 1) ─────────────────
    # `description` es legible para humanos en la UI de gestión.
    # `is_system=True` marca roles que no pueden borrarse desde la UI
    # (admin, editor, monitor, viewer). Ambos los puebla `seed_permissions`.
    description = db.Column(db.String(255), nullable=True)
    is_system   = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    users = db.relationship(
        'User',
        back_populates='role',
        lazy=True
    )

    # ── RBAC: permisos del rol ───────────────────────────────────────────
    # `lazy='select'` (deferred): solo se carga al acceder explícitamente,
    # nunca por listados o serializaciones existentes (RoleSchema solo
    # dumpa id+name). Evita N+1 en endpoints actuales.
    role_permissions = db.relationship(
        'RolePermission',
        back_populates='role',
        cascade='all, delete-orphan',
        lazy='select',
    )

    def __repr__(self):
        return f"<Role {self.id} - {self.name}>"
