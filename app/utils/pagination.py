"""
Utilidad de paginación opt-in para endpoints de listado.

- Si la request NO trae `limit`/`offset`, los endpoints siguen devolviendo la
  lista completa (retrocompatibilidad total).
- Si trae al menos uno, devuelven `{ items, total, limit, offset }`.

`limit` por defecto: 50. `limit` máximo: 200 (para proteger el servidor de
peticiones abusivas).
"""

from typing import Tuple

from flask import request

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def get_pagination_params() -> Tuple[bool, int, int]:
    """
    Lee `?limit=&offset=` de la request.

    Devuelve (paginated, limit, offset):
      - paginated=False si no se enviaron parámetros (modo legacy).
      - paginated=True si se envió alguno; aplica defaults razonables.
    """
    raw_limit = request.args.get("limit")
    raw_offset = request.args.get("offset")

    if raw_limit is None and raw_offset is None:
        return False, 0, 0

    try:
        limit = int(raw_limit) if raw_limit is not None else DEFAULT_LIMIT
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT
    try:
        offset = int(raw_offset) if raw_offset is not None else 0
    except (TypeError, ValueError):
        offset = 0

    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)
    return True, limit, offset


def paginate_query(query, limit: int, offset: int):
    """
    Aplica `OFFSET LIMIT` a una query SQLAlchemy y devuelve (items, total).
    `total` se calcula sin paginar para que el cliente pueda construir UI.
    """
    total = query.order_by(None).count()
    items = query.offset(offset).limit(limit).all()
    return items, total


def envelope(items, total: int, limit: int, offset: int) -> dict:
    """Forma del envelope estándar para respuestas paginadas."""
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
