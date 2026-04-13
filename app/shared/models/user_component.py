from app.core.extensions import db
from datetime import datetime


class UserComponent(db.Model):
    """
    Define a qué componentes tiene acceso un usuario.
    El rol global del usuario (Role) determina qué puede hacer dentro del componente.
    Los admins no necesitan asignaciones — tienen acceso a todo.
    """
    __tablename__ = "user_components"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    component_id = db.Column(
        db.Integer,
        db.ForeignKey("components.id", ondelete="CASCADE"),
        nullable=False
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    user = db.relationship("User", back_populates="component_assignments")
    component = db.relationship("Component", back_populates="user_assignments")

    __table_args__ = (
        db.UniqueConstraint("user_id", "component_id", name="uq_user_component"),
    )

    def __repr__(self):
        return f"<UserComponent user={self.user_id} component={self.component_id}>"