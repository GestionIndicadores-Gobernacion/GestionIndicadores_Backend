from extensions import db
from models.role import role_permission

class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.String(200))

    roles = db.relationship(
        "Role",
        secondary=role_permission,
        back_populates="permissions"
    )
