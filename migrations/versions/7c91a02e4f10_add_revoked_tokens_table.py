"""add revoked_tokens table

Revision ID: 7c91a02e4f10
Revises: ef219ad408af
Create Date: 2026-05-12 10:00:00.000000

Tabla de soporte para el blocklist persistente de JWT (revocación de
access y refresh tokens). Reemplaza el set in-memory que se pierde al
reiniciar el worker.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7c91a02e4f10'
down_revision = 'ef219ad408af'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'revoked_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jti', sa.String(length=36), nullable=False),
        sa.Column('token_type', sa.String(length=10), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jti', name='uq_revoked_tokens_jti'),
    )
    with op.batch_alter_table('revoked_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_revoked_tokens_jti'), ['jti'], unique=False)
        batch_op.create_index(batch_op.f('ix_revoked_tokens_expires_at'), ['expires_at'], unique=False)


def downgrade():
    with op.batch_alter_table('revoked_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_revoked_tokens_expires_at'))
        batch_op.drop_index(batch_op.f('ix_revoked_tokens_jti'))
    op.drop_table('revoked_tokens')
