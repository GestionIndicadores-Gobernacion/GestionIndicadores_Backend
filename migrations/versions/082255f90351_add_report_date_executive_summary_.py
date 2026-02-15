"""Add report_date, executive_summary, activities_performed and zone enum to reports

Revision ID: 082255f90351
Revises: 4b2652c080d6
Create Date: 2026-02-14
"""

from alembic import op
import sqlalchemy as sa


revision = '082255f90351'
down_revision = '4b2652c080d6'
branch_labels = None
depends_on = None


def upgrade():

    bind = op.get_bind()

    # ---------------------------------------------------------
    # 1️⃣ Crear ENUM explícitamente
    # ---------------------------------------------------------
    op.execute("CREATE TYPE zonetypeenum AS ENUM ('URBANA', 'RURAL')")

    # ---------------------------------------------------------
    # 2️⃣ Agregar columnas nuevas (nullable)
    # ---------------------------------------------------------
    op.add_column('reports', sa.Column('report_date', sa.Date(), nullable=True))
    op.add_column('reports', sa.Column('executive_summary', sa.Text(), nullable=True))
    op.add_column('reports', sa.Column('activities_performed', sa.Text(), nullable=True))

    # ---------------------------------------------------------
    # 3️⃣ Backfill datos existentes
    # ---------------------------------------------------------
    op.execute("""
        UPDATE reports
        SET report_date = CURRENT_DATE
        WHERE report_date IS NULL
    """)

    op.execute("""
        UPDATE reports
        SET executive_summary = 'Migrated record'
        WHERE executive_summary IS NULL
    """)

    op.execute("""
        UPDATE reports
        SET activities_performed = 'Migrated record'
        WHERE activities_performed IS NULL
    """)

    # ---------------------------------------------------------
    # 4️⃣ Normalizar valores de zone_type
    # ---------------------------------------------------------
    op.execute("""
        UPDATE reports SET zone_type = 'URBANA'
        WHERE zone_type ILIKE 'Urbana'
    """)

    op.execute("""
        UPDATE reports SET zone_type = 'RURAL'
        WHERE zone_type ILIKE 'Rural'
    """)

    # ---------------------------------------------------------
    # 5️⃣ Convertir VARCHAR → ENUM usando USING
    # ---------------------------------------------------------
    op.execute("""
        ALTER TABLE reports
        ALTER COLUMN zone_type
        TYPE zonetypeenum
        USING zone_type::zonetypeenum
    """)

    # ---------------------------------------------------------
    # 6️⃣ Convertir nuevas columnas a NOT NULL
    # ---------------------------------------------------------
    op.alter_column('reports', 'report_date', nullable=False)
    op.alter_column('reports', 'executive_summary', nullable=False)
    op.alter_column('reports', 'activities_performed', nullable=False)

    # ---------------------------------------------------------
    # 7️⃣ Crear índices
    # ---------------------------------------------------------
    op.create_index('ix_reports_component_id', 'reports', ['component_id'])
    op.create_index('ix_reports_strategy_id', 'reports', ['strategy_id'])
    op.create_index('ix_reports_report_date', 'reports', ['report_date'])


def downgrade():

    # Eliminar índices
    op.drop_index('ix_reports_report_date', table_name='reports')
    op.drop_index('ix_reports_strategy_id', table_name='reports')
    op.drop_index('ix_reports_component_id', table_name='reports')

    # Convertir ENUM → VARCHAR
    op.execute("""
        ALTER TABLE reports
        ALTER COLUMN zone_type
        TYPE VARCHAR(50)
        USING zone_type::text
    """)

    # Eliminar columnas nuevas
    op.drop_column('reports', 'activities_performed')
    op.drop_column('reports', 'executive_summary')
    op.drop_column('reports', 'report_date')

    # Eliminar ENUM
    op.execute("DROP TYPE zonetypeenum")
