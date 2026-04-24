"""
Blacklist de tokens JWT revocados.

Implementación in-memory por worker: **se pierde al reiniciar** y no se
sincroniza entre workers. Suficiente para desarrollo y despliegues
single-worker. Para producción multi-worker migrar a Redis o a una tabla
`revoked_tokens(jti, expires_at)` y reemplazar `_REVOKED` por consulta a esa
tienda — el contrato (funciones `revoke_jti`, `is_jti_revoked`) se mantiene.
"""

from threading import Lock
from typing import Set

_REVOKED: Set[str] = set()
_LOCK = Lock()


def revoke_jti(jti: str) -> None:
    if not jti:
        return
    with _LOCK:
        _REVOKED.add(jti)


def is_jti_revoked(jti: str) -> bool:
    if not jti:
        return False
    with _LOCK:
        return jti in _REVOKED


def clear_all() -> None:
    """Solo para tests."""
    with _LOCK:
        _REVOKED.clear()
