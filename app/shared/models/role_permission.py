from datetime import datetime
from app.core.extensions import db


class RolePermission(db.Model):
    """Asociación rol ↔ permiso (PK compuesta).

    Modelada como clase explícita (no via `secondary=`) para mantener
    parity con el resto del codebase (ej. `ActionPlanResponsibleUser`,
    `UserComponent`) y permitir extensiones futuras como `granted_by`
    sin migrar el modelo.
    """
    __tablename__ = "role_permissions"

    role_id       = db.Column(
        db.Integer,
        db.ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id = db.Column(
        db.Integer,
        db.ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # `lazy='joined'` aquí no afecta a endpoints existentes — solo se
    # dispara cuando algo accede a `role.role_permissions`. Cuando ocurre
    # (evaluación de permisos), evita N+1 cargando el Permission junto.
    role       = db.relationship("Role", back_populates="role_permissions")
    permission = db.relationship("Permission", lazy="joined")

    def __repr__(self):
        return f"<RolePermission role={self.role_id} perm={self.permission_id}>"
