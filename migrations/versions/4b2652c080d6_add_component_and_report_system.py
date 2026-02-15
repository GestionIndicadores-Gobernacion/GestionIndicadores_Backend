"""Add component and report system

Revision ID: 4b2652c080d6
Revises: f8caffe3c047
Create Date: 2026-02-12 14:16:16.436660
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '4b2652c080d6'
down_revision = 'f8caffe3c047'
branch_labels = None
depends_on = None


def upgrade():

    # -----------------------------
    # NUEVAS TABLAS
    # -----------------------------

    op.create_table(
        'component_indicators',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('component_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('field_type', sa.String(length=50), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('is_required', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['component_id'], ['components.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('component_id', 'name', name='uq_indicator_component_name')
    )

    op.create_table(
        'component_mga_activities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('component_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['component_id'], ['components.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'report_indicator_values',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('report_id', sa.Integer(), nullable=False),
        sa.Column('indicator_id', sa.Integer(), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['indicator_id'], ['component_indicators.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('report_id', 'indicator_id', name='uq_report_indicator')
    )

    # -----------------------------
    # COMPONENT_OBJECTIVES
    # -----------------------------

    with op.batch_alter_table('component_objectives') as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=False))
        batch_op.drop_column('created_at')
        batch_op.drop_column('updated_at')
        batch_op.drop_column('objective_name')

    # -----------------------------
    # COMPONENTS
    # -----------------------------

    with op.batch_alter_table('components') as batch_op:
        batch_op.add_column(sa.Column('name', sa.String(length=255), nullable=False))
        batch_op.create_unique_constraint(
            'uq_component_strategy_name',
            ['strategy_id', 'name']
        )
        batch_op.drop_column('component_name')

    # -----------------------------
    # REPORTS (PRIMERO eliminar FKs)
    # -----------------------------

    with op.batch_alter_table('reports') as batch_op:

        batch_op.add_column(sa.Column('intervention_location', sa.String(length=255), nullable=False))
        batch_op.add_column(sa.Column('zone_type', sa.String(length=50), nullable=False))
        batch_op.add_column(sa.Column('evidence_link', sa.Text(), nullable=True))

        # eliminar FKs viejas
        batch_op.drop_constraint(batch_op.f('reports_strategy_id_fkey'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('reports_component_id_fkey'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('reports_created_by_fkey'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('reports_activity_id_fkey'), type_='foreignkey')

        # crear nuevas FKs
        batch_op.create_foreign_key(
            None, 'strategies',
            ['strategy_id'], ['id'],
            ondelete='CASCADE'
        )

        batch_op.create_foreign_key(
            None, 'components',
            ['component_id'], ['id'],
            ondelete='CASCADE'
        )

        # eliminar columnas viejas
        batch_op.drop_column('municipality')
        batch_op.drop_column('activities_performed')
        batch_op.drop_column('description')
        batch_op.drop_column('detail_population')
        batch_op.drop_column('created_by')
        batch_op.drop_column('report_date')
        batch_op.drop_column('evidence_url')
        batch_op.drop_column('activity_id')
        batch_op.drop_column('updated_at')

    # -----------------------------
    # AHORA SÍ ELIMINAR TABLAS VIEJAS
    # -----------------------------

    op.drop_table('indicators')
    op.drop_table('activities_mga')
    op.drop_table('catalog_items')


def downgrade():
    # (no tocamos downgrade, ya estaba correcto)
    pass
