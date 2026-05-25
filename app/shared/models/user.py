from app.core.extensions import db
from datetime import datetime
from app.core.extensions import bcrypt


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    profile_image_url = db.Column(db.String(500), nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # ── RBAC (Bloque 11): admin principal protegido ─────────────────────
    # Reemplaza el hardcode por email en el frontend. Backfilled por la
    # migración. Solo un usuario debería tenerlo en true (no se impone
    # vía constraint para no bloquear ediciones temporales).
    is_main_admin = db.Column(db.Boolean, default=False, nullable=False)

    role_id = db.Column(
        db.Integer,
        db.ForeignKey('roles.id'),
        nullable=False,
        default=1  # viewer por defecto (rol global / fallback)
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relaciones
    role = db.relationship('Role', back_populates='users')

    # ── NUEVO: asignaciones a componentes ────────────────────────────────
    component_assignments = db.relationship(
        "UserComponent",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    # ── RBAC: overrides personales (grant/revoke) ────────────────────────
    # `lazy='select'` (deferred): no se carga automáticamente en /users/me,
    # /users/, login ni en ningún serializador existente. Solo el evaluador
    # de permisos (Bloque 5) lo accederá explícitamente.
    # `foreign_keys=...` apunta solo al user_id; el campo granted_by tiene
    # su propia relación en UserPermission (no inverse aquí).
    permission_overrides = db.relationship(
        "UserPermission",
        foreign_keys="UserPermission.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # ======================
    # Password helpers
    # ======================
    def set_password(self, password: str):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.id} - {self.email}>"