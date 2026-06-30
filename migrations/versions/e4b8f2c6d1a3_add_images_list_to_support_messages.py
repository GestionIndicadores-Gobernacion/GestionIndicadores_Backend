"""add images list to support_messages

Revision ID: e4b8f2c6d1a3
Revises: d3a7e1c45b22
Create Date: 2026-06-30 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e4b8f2c6d1a3'
down_revision = 'd3a7e1c45b22'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('support_messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('images', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('support_messages', schema=None) as batch_op:
        batch_op.drop_column('images')
