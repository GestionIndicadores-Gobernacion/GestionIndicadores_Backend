"""add rbac permissions tables

Revision ID: a1b2c3e7f8d9
Revises: 7c91a02e4f10
Create Date: 2026-05-20 12:00:00.000000

Introduce el modelo RBAC híbrido sin tocar aún ningún endpoint:

- `roles`: añade columnas `description` (texto legible para UI admin) y
  `is_system` (true = no borrable desde UI). Ambos NULL/false por defecto
  para no romper filas existentes; el seeder los puebla.
- `permissions`: catálogo de permisos definidos en código. El seeder
  upserta filas por `code`. Solo se exponen vía UI para administrar; no se
  crean desde el frontend.
- `role_permissions`: relación m:n rol ↔ permiso.
- `user_permissions`: overrides por usuario (`effect = grant|revoke`).

Toda la lógica de runtime existente (role.name, role_required) sigue
intacta después de esta migración. Es puramente esquema.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3e7f8d9'
down_revision = '7c91a02e4f10'
branch_labels = None
depends_on = None


def upgrade():
    # ── roles: añadir description e is_system ───────────────────────────
    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column(
            'is_system',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ))

    # ── permissions ──────────────────────────────────────────────────────
    op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=80), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('module', sa.String(length=50), nullable=False),
        sa.Column(
            'is_system',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_permissions_code'),
    )
    with op.batch_alter_table('permissions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_permissions_module'), ['module'], unique=False)

    # ── role_permissions ─────────────────────────────────────────────────
    op.create_table(
        'role_permissions',
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('role_id', 'permission_id', name='pk_role_permissions'),
    )

    # ── user_permissions ─────────────────────────────────────────────────
    op.create_table(
        'user_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column(
            'effect',
            sa.Enum('grant', 'revoke', name='user_permission_effect'),
            nullable=False,
        ),
        sa.Column('granted_by', sa.Integer(), nullable=True),
        sa.Column('granted_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'permission_id', name='uq_user_permission'),
    )
    with op.batch_alter_table('user_permissions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_permissions_user_id'), ['user_id'], unique=False)


def downgrade():
    # Orden inverso: primero las tablas que referencian permissions/roles,
    # luego permissions, y al final las columnas añadidas a roles.
    with op.batch_alter_table('user_permissions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_permissions_user_id'))
    op.drop_table('user_permissions')

    op.drop_table('role_permissions')

    with op.batch_alter_table('permissions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_permissions_module'))
    op.drop_table('permissions')

    with op.batch_alter_table('roles', schema=None) as batch_op:
        batch_op.drop_column('is_system')
        batch_op.drop_column('description')

    # En Postgres el tipo enum queda huérfano tras drop_table; en SQLite no
    # existe. Lo limpiamos solo si el dialecto lo soporta para no romper
    # en SQLite (donde DROP TYPE no existe).
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        sa.Enum(name='user_permission_effect').drop(bind, checkfirst=True)
