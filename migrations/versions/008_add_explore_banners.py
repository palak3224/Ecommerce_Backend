"""add explore_banners table

Revision ID: 008_add_explore_banners
Revises: 007_reels_external_price
Create Date: 2026-07-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '008_add_explore_banners'
down_revision = '007_reels_external_price'
branch_labels = None
depends_on = None


def upgrade():
    """Create the explore_banners table (mobile app Explore screen banners)."""
    op.create_table(
        'explore_banners',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('slot', sa.String(length=20), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('cta_text', sa.String(length=100), nullable=False),
        sa.Column('cta_path', sa.String(length=500), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('explore_banners')
