"""remove code from catalog_items

Revision ID: 53163265ea95
Revises: c122cc23a855
Create Date: 2026-02-03 14:45:00.791221
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '53163265ea95'
down_revision = 'c122cc23a855'
branch_labels = None
depends_on = None


def upgrade():
    # eliminar constraint viejo (si existe)
    op.drop_constraint(
        'uq_catalog_code',
        'catalog_items',
        type_='unique'
    )

    # eliminar columna code
    op.drop_column('catalog_items', 'code')

    # nuevo constraint por (catalog, name)
    op.create_unique_constraint(
        'uq_catalog_name',
        'catalog_items',
        ['catalog', 'name']
    )


def downgrade():
    # volver a crear columna code
    op.add_column(
        'catalog_items',
        sa.Column('code', sa.String(length=100), nullable=False)
    )

    # eliminar nuevo constraint
    op.drop_constraint(
        'uq_catalog_name',
        'catalog_items',
        type_='unique'
    )

    # restaurar constraint viejo
    op.create_unique_constraint(
        'uq_catalog_code',
        'catalog_items',
        ['catalog', 'code']
    )
