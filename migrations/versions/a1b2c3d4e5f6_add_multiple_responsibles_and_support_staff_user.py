"""add multiple responsibles and support staff user id

Revision ID: a1b2c3d4e5f6
Revises: 74f5414c30da
Branch_labels = None
Depends_on = None
Create Date: 2026-04-14 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '74f5414c30da'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Tabla de múltiples responsables por plan
    op.create_table(
        'action_plan_responsible_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('action_plan_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['action_plan_id'], ['action_plans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('action_plan_id', 'user_id', name='uq_plan_responsible_user'),
    )
    op.create_index('ix_action_plan_responsible_users_plan', 'action_plan_responsible_users', ['action_plan_id'])
    op.create_index('ix_action_plan_responsible_users_user', 'action_plan_responsible_users', ['user_id'])

    # 2. user_id en personal de apoyo (opcional, para vincular con usuario existente)
    with op.batch_alter_table('action_plan_support_staff', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_support_staff_user',
            'users',
            ['user_id'],
            ['id'],
            ondelete='SET NULL'
        )
        batch_op.create_index('ix_support_staff_user_id', ['user_id'])


def downgrade():
    with op.batch_alter_table('action_plan_support_staff', schema=None) as batch_op:
        batch_op.drop_index('ix_support_staff_user_id')
        batch_op.drop_constraint('fk_support_staff_user', type_='foreignkey')
        batch_op.drop_column('user_id')

    op.drop_index('ix_action_plan_responsible_users_user', table_name='action_plan_responsible_users')
    op.drop_index('ix_action_plan_responsible_users_plan', table_name='action_plan_responsible_users')
    op.drop_table('action_plan_responsible_users')
