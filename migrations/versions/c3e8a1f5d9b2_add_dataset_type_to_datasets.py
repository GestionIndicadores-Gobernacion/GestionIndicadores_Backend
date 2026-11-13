"""add datasets.dataset_type (tipo de dashboard persistido)

El dashboard de cada dataset se decidía re-detectando columnas en cada
render; si un corte mensual traía encabezados distintos el dataset caía en el
dashboard genérico. Ahora el tipo queda guardado en el dataset.

  1. Agrega ``datasets.dataset_type`` (VARCHAR(50), NULL) si no existe.
  2. Rellena SOLO las filas con ``dataset_type IS NULL`` detectando el tipo
     con las columnas (``fields.name``) ya cargadas. No toca tablas, campos
     ni registros.

Idempotente y no destructiva: se puede correr varias veces; el downgrade
solo elimina la columna nueva.

Revision ID: c3e8a1f5d9b2
Revises: b7d2e9a4c1f6
Create Date: 2026-11-12 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3e8a1f5d9b2'
down_revision = 'b7d2e9a4c1f6'
branch_labels = None
depends_on = None


def _has_column(bind, table, column):
    return any(c["name"] == column for c in sa.inspect(bind).get_columns(table))


def upgrade():
    bind = op.get_bind()

    if not _has_column(bind, "datasets", "dataset_type"):
        op.add_column("datasets", sa.Column("dataset_type", sa.String(length=50), nullable=True))

    # Backfill con la misma lógica de detección que usa la app.
    from app.modules.datasets.dashboard.dataset_types import (
        GENERIC, detect_type_from_names, is_specific,
    )

    pending = bind.execute(sa.text(
        "SELECT id FROM datasets WHERE dataset_type IS NULL ORDER BY id"
    )).fetchall()

    for (dataset_id,) in pending:
        table_ids = [r[0] for r in bind.execute(sa.text(
            "SELECT id FROM tables WHERE dataset_id = :d ORDER BY id"
        ), {"d": dataset_id}).fetchall()]

        dtype = GENERIC
        for table_id in table_ids:
            names = [r[0] for r in bind.execute(sa.text(
                "SELECT name FROM fields WHERE table_id = :t"
            ), {"t": table_id}).fetchall()]
            detected = detect_type_from_names(names)
            if is_specific(detected):
                dtype = detected
                break

        bind.execute(sa.text(
            "UPDATE datasets SET dataset_type = :t "
            "WHERE id = :d AND dataset_type IS NULL"
        ), {"t": dtype, "d": dataset_id})


def downgrade():
    bind = op.get_bind()
    if _has_column(bind, "datasets", "dataset_type"):
        op.drop_column("datasets", "dataset_type")
