"""add read_by_admin + composite unread indexes to support_messages

Revision ID: f5c9a3d7e210
Revises: e4b8f2c6d1a3
Create Date: 2026-07-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f5c9a3d7e210'
down_revision = 'e4b8f2c6d1a3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('support_messages', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('read_by_admin', sa.Boolean(), nullable=False,
                      server_default=sa.false())
        )
        batch_op.create_index(
            'ix_support_msg_owner_unread',
            ['ticket_id', 'is_admin_reply', 'read_by_owner'],
        )
        batch_op.create_index(
            'ix_support_msg_admin_unread',
            ['ticket_id', 'is_admin_reply', 'read_by_admin'],
        )

    # El histórico se marca como "ya visto por el admin" para no inundar el
    # nuevo badge con mensajes antiguos; el default para filas nuevas es False.
    op.execute("UPDATE support_messages SET read_by_admin = true")


def downgrade():
    with op.batch_alter_table('support_messages', schema=None) as batch_op:
        batch_op.drop_index('ix_support_msg_admin_unread')
        batch_op.drop_index('ix_support_msg_owner_unread')
        batch_op.drop_column('read_by_admin')
