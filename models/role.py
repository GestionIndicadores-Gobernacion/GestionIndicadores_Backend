from db import db

# 🔥 Primero tabla intermedia
user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True)
)

from models.permission import role_permissions  # 👈 Se importa después para evitar ciclo

class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))

    # 👇 RELACIÓN CORRECTA (Debe coincidir)
    users = db.relationship("User", secondary=user_roles, back_populates="roles")

    permissions = db.relationship("Permission", secondary=role_permissions, back_populates="roles")
