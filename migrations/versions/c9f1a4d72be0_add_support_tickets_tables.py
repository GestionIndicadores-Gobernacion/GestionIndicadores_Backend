"""add support tickets tables

Revision ID: c9f1a4d72be0
Revises: b2c4d6e8f0a1
Create Date: 2026-05-26 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c9f1a4d72be0'
down_revision = 'b2c4d6e8f0a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'support_tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('current_url', sa.String(length=1000), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pendiente'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('support_tickets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_support_tickets_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_support_tickets_status'), ['status'], unique=False)

    op.create_table(
        'support_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_admin_reply', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('read_by_owner', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('support_messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_support_messages_ticket_id'), ['ticket_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_support_messages_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('support_messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_support_messages_user_id'))
        batch_op.drop_index(batch_op.f('ix_support_messages_ticket_id'))
    op.drop_table('support_messages')

    with op.batch_alter_table('support_tickets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_support_tickets_status'))
        batch_op.drop_index(batch_op.f('ix_support_tickets_user_id'))
    op.drop_table('support_tickets')
