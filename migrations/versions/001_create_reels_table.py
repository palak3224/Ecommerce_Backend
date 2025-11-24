"""create reels table

Revision ID: 001_create_reels
Revises: 
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision = '001_create_reels'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create reels table."""
    op.create_table(
        'reels',
        sa.Column('reel_id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('merchant_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        
        # Video storage
        sa.Column('video_url', sa.String(length=512), nullable=False),
        sa.Column('video_public_id', sa.String(length=255), nullable=True),
        sa.Column('thumbnail_url', sa.String(length=512), nullable=True),
        sa.Column('thumbnail_public_id', sa.String(length=255), nullable=True),
        
        # Metadata
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('video_format', sa.String(length=10), nullable=True),
        sa.Column('resolution', sa.String(length=20), nullable=True),
        
        # Stats
        sa.Column('views_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('likes_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('shares_count', sa.Integer(), nullable=False, server_default='0'),
        
        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('approval_status', sa.String(length=20), nullable=False, server_default='approved'),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('rejection_reason', sa.String(length=255), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp()),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['merchant_id'], ['merchant_profiles.id'], name='fk_reels_merchant'),
        sa.ForeignKeyConstraint(['product_id'], ['products.product_id'], name='fk_reels_product'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], name='fk_reels_approved_by'),
        
        # Primary key
        sa.PrimaryKeyConstraint('reel_id', name='pk_reels')
    )
    
    # Create indexes
    op.create_index('idx_reels_merchant_id', 'reels', ['merchant_id'])
    op.create_index('idx_reels_product_id', 'reels', ['product_id'])
    op.create_index('idx_reels_is_active', 'reels', ['is_active'])
    op.create_index('idx_reels_approval_status', 'reels', ['approval_status'])
    op.create_index('idx_reels_created_at', 'reels', ['created_at'])
    op.create_index('idx_reels_deleted_at', 'reels', ['deleted_at'])


def downgrade():
    """Drop reels table."""
    op.drop_index('idx_reels_deleted_at', table_name='reels')
    op.drop_index('idx_reels_created_at', table_name='reels')
    op.drop_index('idx_reels_approval_status', table_name='reels')
    op.drop_index('idx_reels_is_active', table_name='reels')
    op.drop_index('idx_reels_product_id', table_name='reels')
    op.drop_index('idx_reels_merchant_id', table_name='reels')
    op.drop_table('reels')

