"""add direct_messages table

Revision ID: a1b2c3d4e5f6
Revises: 36f702dd00e7
Create Date: 2026-05-07 15:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '36f702dd00e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'direct_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('sender_user_id', sa.UUID(), nullable=False),
        sa.Column('recipient_user_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_direct_messages_tenant_id'), 'direct_messages', ['tenant_id'])
    op.create_index(op.f('ix_direct_messages_sender_user_id'), 'direct_messages', ['sender_user_id'])
    op.create_index(op.f('ix_direct_messages_recipient_user_id'), 'direct_messages', ['recipient_user_id'])
    op.create_index(op.f('ix_direct_messages_created_at'), 'direct_messages', ['created_at'])
    op.create_index(
        'ix_dm_thread',
        'direct_messages',
        ['tenant_id', 'sender_user_id', 'recipient_user_id', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_dm_thread', table_name='direct_messages')
    op.drop_index(op.f('ix_direct_messages_created_at'), table_name='direct_messages')
    op.drop_index(op.f('ix_direct_messages_recipient_user_id'), table_name='direct_messages')
    op.drop_index(op.f('ix_direct_messages_sender_user_id'), table_name='direct_messages')
    op.drop_index(op.f('ix_direct_messages_tenant_id'), table_name='direct_messages')
    op.drop_table('direct_messages')
