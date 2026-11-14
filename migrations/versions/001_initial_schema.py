"""initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-14 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Sessions table
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
    )
    op.create_index('ix_sessions_token_hash', 'sessions', ['token_hash'], unique=True)
    op.create_index('ix_sessions_expires_at', 'sessions', ['expires_at'])

    # 2. Bonbons table
    op.create_table(
        'bonbons',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('shell', sa.String(length=20), nullable=False, server_default='dark'),
        sa.Column('category', sa.String(length=20), nullable=False, server_default='seasonal'),
        sa.Column('allergens', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('primary_image_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_bonbons_slug', 'bonbons', ['slug'], unique=True)
    op.create_index('ix_bonbons_is_active', 'bonbons', ['is_active'])
    op.create_index('ix_bonbons_category', 'bonbons', ['category'])
    op.create_index('ix_bonbons_sort_order', 'bonbons', ['sort_order'])

    # 3. Bonbon Images table
    op.create_table(
        'bonbon_images',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('bonbon_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('raw_filename', sa.String(length=255), nullable=False),
        sa.Column('processed_filename', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('width', sa.Integer(), nullable=False, server_default='500'),
        sa.Column('height', sa.Integer(), nullable=False, server_default='500'),
        sa.Column('model_used', sa.String(length=50), nullable=False, server_default='birefnet-general-lite'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['bonbon_id'], ['bonbons.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_bonbon_images_bonbon_id', 'bonbon_images', ['bonbon_id'])

    # 4. Foreign key from bonbons to bonbon_images
    op.create_foreign_key(
        'fk_bonbons_primary_image_id',
        'bonbons',
        'bonbon_images',
        ['primary_image_id'],
        ['id'],
        ondelete='SET NULL',
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint('fk_bonbons_primary_image_id', 'bonbons', type_='foreignkey')
    op.drop_table('bonbon_images')
    op.drop_table('bonbons')
    op.drop_table('sessions')
