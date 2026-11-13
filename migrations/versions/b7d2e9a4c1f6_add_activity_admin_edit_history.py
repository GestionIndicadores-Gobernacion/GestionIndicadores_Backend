"""add action_plan_activity_changes + permiso action_plans.edit_reported

Corrección administrativa de actividades ya reportadas:
  1. Tabla permanente de historial por campo (no se purga como audit_logs).
  2. Alta del permiso `action_plans.edit_reported` y asignación al rol
     `admin` (los bundles de `flask seed_permissions` solo se aplican a roles
     vacíos, así que en ambientes ya seedeados el grant debe hacerse aquí).

Revision ID: b7d2e9a4c1f6
Revises: f5c9a3d7e210
Create Date: 2026-11-12 10:00:00.000000

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = 'b7d2e9a4c1f6'
down_revision = 'f5c9a3d7e210'
branch_labels = None
depends_on = None


PERM_CODE = "action_plans.edit_reported"
PERM_DESC = "Corregir actividades ya reportadas (solo admin)"


def upgrade():
    op.create_table(
        'action_plan_activity_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('activity_id', sa.Integer(), nullable=True),
        sa.Column('action_plan_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('change_group', sa.String(length=36), nullable=False),
        sa.Column('field', sa.String(length=50), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['activity_id'], ['action_plan_activities.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('action_plan_activity_changes', schema=None) as batch_op:
        batch_op.create_index('ix_action_plan_activity_changes_activity_id', ['activity_id'])
        batch_op.create_index('ix_action_plan_activity_changes_action_plan_id', ['action_plan_id'])
        batch_op.create_index('ix_action_plan_activity_changes_user_id', ['user_id'])
        batch_op.create_index('ix_action_plan_activity_changes_change_group', ['change_group'])

    # ── Permiso + grant al rol admin (idempotente) ──────────────────────
    conn = op.get_bind()
    now = datetime.utcnow()
    perm_id = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = :c"), {"c": PERM_CODE}
    ).scalar()
    if perm_id is None:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, description, module, is_system, created_at) "
                "VALUES (:c, :d, 'action_plans', :sys, :now)"
            ),
            {"c": PERM_CODE, "d": PERM_DESC, "sys": True, "now": now},
        )
        perm_id = conn.execute(
            sa.text("SELECT id FROM permissions WHERE code = :c"), {"c": PERM_CODE}
        ).scalar()

    admin_role_id = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'admin'")
    ).scalar()
    if admin_role_id is not None and perm_id is not None:
        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM role_permissions WHERE role_id = :r AND permission_id = :p"
            ),
            {"r": admin_role_id, "p": perm_id},
        ).scalar()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id, created_at) "
                    "VALUES (:r, :p, :now)"
                ),
                {"r": admin_role_id, "p": perm_id, "now": now},
            )


def downgrade():
    conn = op.get_bind()
    perm_id = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = :c"), {"c": PERM_CODE}
    ).scalar()
    if perm_id is not None:
        conn.execute(sa.text("DELETE FROM role_permissions WHERE permission_id = :p"), {"p": perm_id})
        conn.execute(sa.text("DELETE FROM user_permissions WHERE permission_id = :p"), {"p": perm_id})
        conn.execute(sa.text("DELETE FROM permissions WHERE id = :p"), {"p": perm_id})

    with op.batch_alter_table('action_plan_activity_changes', schema=None) as batch_op:
        batch_op.drop_index('ix_action_plan_activity_changes_change_group')
        batch_op.drop_index('ix_action_plan_activity_changes_user_id')
        batch_op.drop_index('ix_action_plan_activity_changes_action_plan_id')
        batch_op.drop_index('ix_action_plan_activity_changes_activity_id')
    op.drop_table('action_plan_activity_changes')
