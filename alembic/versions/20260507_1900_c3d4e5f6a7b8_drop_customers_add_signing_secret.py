"""drop customers table; add tenants.signing_secret

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-07 19:00:00.000000+00:00

"""
import secrets
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) tenants.signing_secret column (start nullable, backfill, then NOT NULL)
    op.add_column(
        'tenants',
        sa.Column('signing_secret', sa.String(length=128), nullable=True),
    )
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM tenants WHERE signing_secret IS NULL")).fetchall()
    for row in rows:
        bind.execute(
            sa.text("UPDATE tenants SET signing_secret = :s WHERE id = :id"),
            {"s": secrets.token_urlsafe(32), "id": row[0]},
        )
    op.alter_column('tenants', 'signing_secret', nullable=False)

    # 2) drop customers table (and its indexes)
    try:
        op.drop_index(op.f('ix_customers_chatwoot_contact_id'), table_name='customers')
    except Exception:
        pass
    try:
        op.drop_index(op.f('ix_customers_email'), table_name='customers')
    except Exception:
        pass
    op.drop_table('customers')


def downgrade() -> None:
    op.create_table(
        'customers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('chatwoot_contact_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_customers_email'), 'customers', ['email'], unique=True)
    op.create_index(
        op.f('ix_customers_chatwoot_contact_id'),
        'customers',
        ['chatwoot_contact_id'],
    )
    op.drop_column('tenants', 'signing_secret')
