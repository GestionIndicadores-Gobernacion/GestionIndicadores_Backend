"""add users.is_main_admin + backfill

Revision ID: b2c4d6e8f0a1
Revises: a1b2c3e7f8d9
Create Date: 2026-05-20 13:00:00.000000

Introduce `users.is_main_admin BOOLEAN NOT NULL DEFAULT FALSE` y
backfilea el flag para reemplazar el hardcode por email que existe en
el frontend (`user-form.ts`).

Heurística del backfill:
  1) Si existe un usuario con email = 'admin@gobernacion.gov.co' → es el
     main admin (consistente con el seed actual).
  2) Si no, el PRIMER usuario con rol 'admin' (por id ascendente) queda
     marcado como main admin. Esto cubre ambientes donde el email
     seedeado ya fue renombrado.
  3) Si no hay ningún admin, no se marca a nadie. El operador deberá
     marcarlo manualmente cuando cree el primer admin.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c4d6e8f0a1'
down_revision = 'a1b2c3e7f8d9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'is_main_admin',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ))

    bind = op.get_bind()

    # Estrategia 1: usuario seedeado por email.
    seeded_email = 'admin@gobernacion.gov.co'
    result = bind.execute(
        sa.text("SELECT id FROM users WHERE email = :email LIMIT 1"),
        {"email": seeded_email},
    ).fetchone()

    target_user_id = None
    if result:
        target_user_id = result[0]
    else:
        # Estrategia 2: primer admin por id.
        admin_role = bind.execute(
            sa.text("SELECT id FROM roles WHERE name = 'admin' LIMIT 1")
        ).fetchone()
        if admin_role:
            first_admin = bind.execute(
                sa.text(
                    "SELECT id FROM users WHERE role_id = :role_id "
                    "ORDER BY id ASC LIMIT 1"
                ),
                {"role_id": admin_role[0]},
            ).fetchone()
            if first_admin:
                target_user_id = first_admin[0]

    if target_user_id is not None:
        bind.execute(
            sa.text("UPDATE users SET is_main_admin = TRUE WHERE id = :uid"),
            {"uid": target_user_id},
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_main_admin')
