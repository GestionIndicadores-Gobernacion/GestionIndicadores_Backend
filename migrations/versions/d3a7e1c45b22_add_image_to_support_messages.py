"""add image_data_url to support_messages

Revision ID: d3a7e1c45b22
Revises: c9f1a4d72be0
Create Date: 2026-06-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd3a7e1c45b22'
down_revision = 'c9f1a4d72be0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('support_messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_data_url', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('support_messages', schema=None) as batch_op:
        batch_op.drop_column('image_data_url')
