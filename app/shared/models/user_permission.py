from datetime import datetime
from app.core.extensions import db


class UserPermission(db.Model):
    """Override por usuario sobre el conjunto heredado del rol.

    - `effect='grant'`  → otorga un permiso que el rol del usuario no tiene.
    - `effect='revoke'` → quita un permiso que el rol del usuario sí da.

    El cálculo de permisos efectivos es:
        permisos_del_rol(user) ∪ grants(user) − revokes(user)

    `UNIQUE(user_id, permission_id)` evita duplicados — un usuario tiene
    a lo sumo un override por permiso (grant XOR revoke).
    """
    __tablename__ = "user_permissions"

    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id = db.Column(
        db.Integer,
        db.ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    effect        = db.Column(
        db.Enum("grant", "revoke", name="user_permission_effect"),
        nullable=False,
    )
    granted_by    = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    granted_at    = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "permission_id", name="uq_user_permission"),
    )

    # `foreign_keys` explícito porque hay dos FKs a `users` (user_id y
    # granted_by). Sin esto, SQLAlchemy no puede inferir cuál usar.
    user            = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="permission_overrides",
    )
    permission      = db.relationship("Permission", lazy="joined")
    granted_by_user = db.relationship("User", foreign_keys=[granted_by])

    def __repr__(self):
        return f"<UserPermission user={self.user_id} perm={self.permission_id} effect={self.effect}>"
