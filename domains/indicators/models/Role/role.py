from extensions import db

from datetime import datetime


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(50), unique=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    users = db.relationship(
        'User',
        back_populates='role',
        lazy=True
    )

    def __repr__(self):
        return f"<Role {self.id} - {self.name}>"
