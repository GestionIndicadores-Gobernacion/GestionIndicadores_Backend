"""add strategy annual goals

Revision ID: f8caffe3c047
Revises: 46643428ef89
Create Date: 2026-02-12 11:47:25.824323
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8caffe3c047'
down_revision = '46643428ef89'
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------
    # 1️⃣ Agregar columnas nuevas (permitiendo NULL temporalmente)
    # ------------------------------------------------------------------
    op.add_column('strategies', sa.Column('name', sa.String(length=255), nullable=True))
    op.add_column('strategies', sa.Column('objective', sa.Text(), nullable=True))
    op.add_column('strategies', sa.Column('product_goal_description', sa.Text(), nullable=True))

    # ------------------------------------------------------------------
    # 2️⃣ Migrar datos existentes → nuevo modelo
    # ------------------------------------------------------------------
    op.execute("""
        UPDATE strategies
        SET
            name = strategy_name,
            objective = general_objective,
            product_goal_description = product_goal
    """)

    # ------------------------------------------------------------------
    # 3️⃣ Ahora sí hacer las columnas obligatorias
    # ------------------------------------------------------------------
    op.alter_column('strategies', 'name', nullable=False)
    op.alter_column('strategies', 'objective', nullable=False)
    op.alter_column('strategies', 'product_goal_description', nullable=False)

    # ------------------------------------------------------------------
    # 4️⃣ Crear la nueva tabla relacional de metas anuales
    # ------------------------------------------------------------------
    op.create_table(
        'strategy_annual_goals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('strategy_id', sa.Integer(), nullable=False),
        sa.Column('year_number', sa.Integer(), nullable=False),
        sa.Column('value', sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(['strategy_id'], ['strategies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('strategy_id', 'year_number', name='uq_strategy_year')
    )

    # ------------------------------------------------------------------
    # 5️⃣ Eliminar columnas viejas (ya migramos los datos)
    # ------------------------------------------------------------------
    op.drop_column('strategies', 'strategy_name')
    op.drop_column('strategies', 'product_goal')
    op.drop_column('strategies', 'reporting_method')
    op.drop_column('strategies', 'general_objective')


def downgrade():
    # ------------------------------------------------------------------
    # 1️⃣ Volver a crear columnas antiguas (permitiendo NULL)
    # ------------------------------------------------------------------
    op.add_column('strategies', sa.Column('strategy_name', sa.String(length=255), nullable=True))
    op.add_column('strategies', sa.Column('product_goal', sa.Text(), nullable=True))
    op.add_column('strategies', sa.Column('reporting_method', sa.Text(), nullable=True))
    op.add_column('strategies', sa.Column('general_objective', sa.Text(), nullable=True))

    # ------------------------------------------------------------------
    # 2️⃣ Restaurar los datos al esquema anterior
    # ------------------------------------------------------------------
    op.execute("""
        UPDATE strategies
        SET
            strategy_name = name,
            product_goal = product_goal_description,
            general_objective = objective
    """)

    # ------------------------------------------------------------------
    # 3️⃣ Eliminar tabla nueva
    # ------------------------------------------------------------------
    op.drop_table('strategy_annual_goals')

    # ------------------------------------------------------------------
    # 4️⃣ Eliminar columnas nuevas
    # ------------------------------------------------------------------
    op.drop_column('strategies', 'name')
    op.drop_column('strategies', 'objective')
    op.drop_column('strategies', 'product_goal_description')
