"""Blocklist persistente de JWT revocados.

Antes era un set in-memory por worker (se perdía al reiniciar y no se
sincronizaba entre workers). Ahora persiste en la tabla `revoked_tokens`
(ver migración `7c91a02e4f10`), de modo que:

* Sobrevive reinicios y deploys.
* Es coherente entre múltiples workers gunicorn.
* Permite purgar entradas cuyo JWT ya venció por sí mismo (limpieza
  opcional vía `purge_expired`).

La API pública se mantiene (`revoke_jti`, `is_jti_revoked`, `clear_all`)
para no obligar a cambios en `error_handlers.py` ni en las rutas.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError

from app.core.extensions import db
from app.shared.models.revoked_token import RevokedToken


def revoke_jti(
    jti: str,
    token_type: str = "access",
    expires_at: Optional[datetime] = None,
) -> None:
    """Marca un jti como revocado. Idempotente.

    `expires_at` debe ser timezone-aware (UTC). Si no se conoce, se usa
    un fallback de 30 días (vida máxima del refresh) para que la fila
    sobreviva hasta entonces y la purga la elimine después.
    """
    if not jti:
        return

    if expires_at is None:
        # Fallback defensivo: nunca debería pasar — los callers conocen
        # `exp` del payload. Se usa un techo de 30 días para que la fila
        # cubra hasta la vida máxima del refresh configurado.
        from datetime import timedelta
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    elif expires_at.tzinfo is None:
        # JWT `exp` viene como int (epoch). Si el caller lo construyó
        # naive por error, lo asumimos UTC.
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    entry = RevokedToken(jti=jti, token_type=token_type, expires_at=expires_at)
    db.session.add(entry)
    try:
        db.session.commit()
    except IntegrityError:
        # Otro request / worker ya lo registró: la unicidad de `jti`
        # garantiza que el efecto deseado (jti revocado) se cumpla.
        db.session.rollback()


def is_jti_revoked(jti: str) -> bool:
    if not jti:
        return False
    return db.session.query(
        RevokedToken.query.filter_by(jti=jti).exists()
    ).scalar()


def clear_all() -> None:
    """Solo para tests."""
    RevokedToken.query.delete()
    db.session.commit()


def purge_expired() -> int:
    """Elimina entradas cuyo JWT ya expiró por sí mismo. Retorna cantidad."""
    now = datetime.now(timezone.utc)
    deleted = RevokedToken.query.filter(RevokedToken.expires_at < now).delete(
        synchronize_session=False
    )
    db.session.commit()
    return deleted
