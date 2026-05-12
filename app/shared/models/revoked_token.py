from datetime import datetime, timezone

from app.core.extensions import db


class RevokedToken(db.Model):
    """JTIs revocados (access / refresh).

    El callback `token_in_blocklist_loader` consulta esta tabla en cada
    request con `@jwt_required`. La columna `expires_at` permite purgar
    filas cuyo token JWT ya venció por sí mismo (no aporta seguridad
    seguir guardándolas).
    """

    __tablename__ = "revoked_tokens"

    id = db.Column(db.Integer, primary_key=True)

    jti = db.Column(db.String(36), nullable=False, unique=True, index=True)
    token_type = db.Column(db.String(10), nullable=False)  # "access" | "refresh"
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<RevokedToken {self.token_type} {self.jti[:8]}...>"
