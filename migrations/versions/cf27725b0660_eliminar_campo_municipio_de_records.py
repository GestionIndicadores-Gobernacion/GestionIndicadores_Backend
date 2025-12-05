"""Eliminar campo municipio de records

Revision ID: cf27725b0660
Revises: 9eddc2f54e65
Create Date: 2025-12-02 13:52:53.657834

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf27725b0660'
down_revision = '9eddc2f54e65'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('records', schema=None) as batch_op:
        batch_op.drop_column('municipio')


def downgrade():
    with op.batch_alter_table('records', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'municipio',
                sa.String(length=150),
                nullable=False,
                server_default=""
            )
        )
