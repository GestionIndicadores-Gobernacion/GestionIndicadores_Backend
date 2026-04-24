"""fix missing tables / add updated_at to datasets

Revision ID: ef219ad408af
Revises: a1b2c3d4e5f6
Create Date: 2026-04-24 15:36:01.292102

NOTA:
    Esta migración fue regenerada para ser IDEMPOTENTE.
    Originalmente intentaba `create_table('datasets', ...)` y otras tablas que
    en bases de datos ya inicializadas existen, causando DuplicateTable.
    Ahora únicamente añade la columna `datasets.updated_at` si falta.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ef219ad408af'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "datasets" not in inspector.get_table_names():
        # Caso poco común: BD vacía. Crear solo la tabla mínima requerida.
        op.create_table(
            "datasets",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        return

    if not _has_column(inspector, "datasets", "updated_at"):
        with op.batch_alter_table("datasets", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("updated_at", sa.DateTime(), nullable=True)
            )
        op.execute(
            "UPDATE datasets SET updated_at = created_at WHERE updated_at IS NULL"
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_column(inspector, "datasets", "updated_at"):
        with op.batch_alter_table("datasets", schema=None) as batch_op:
            batch_op.drop_column("updated_at")
