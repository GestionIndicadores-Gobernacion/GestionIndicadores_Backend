"""add activity report integration

Revision ID: 74f5414c30da
Revises: 0dc7c01f341f
Create Date: 2026-04-09 14:06:34.886800
"""
from alembic import op
import sqlalchemy as sa


revision = '74f5414c30da'
down_revision = '0dc7c01f341f'
branch_labels = None
depends_on = None


def upgrade():

    # 1️⃣ Crear la columna permitiendo NULL
    with op.batch_alter_table('action_plan_activities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('generates_report', sa.Boolean(), nullable=True))

    # 2️⃣ Llenar los registros existentes
    op.execute(
        "UPDATE action_plan_activities SET generates_report = FALSE"
    )

    # 3️⃣ Convertir la columna a NOT NULL
    with op.batch_alter_table('action_plan_activities', schema=None) as batch_op:
        batch_op.alter_column(
            'generates_report',
            existing_type=sa.Boolean(),
            nullable=False
        )

    # Cambios en reports
    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('action_plan_activity_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_reports_action_plan_activity_id'),
            ['action_plan_activity_id'],
            unique=True
        )
        batch_op.create_foreign_key(
            None,
            'action_plan_activities',
            ['action_plan_activity_id'],
            ['id'],
            ondelete='SET NULL'
        )


def downgrade():

    with op.batch_alter_table('reports', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_reports_action_plan_activity_id'))
        batch_op.drop_column('action_plan_activity_id')

    with op.batch_alter_table('action_plan_activities', schema=None) as batch_op:
        batch_op.drop_column('generates_report')