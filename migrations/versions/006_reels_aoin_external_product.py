"""reels AOIN and external product support

Revision ID: 006_reels_aoin_external
Revises: 005_add_category_is_active
Create Date: 2025-02-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '006_reels_aoin_external'
down_revision = '005_add_category_is_active'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns (nullable)
    op.add_column('reels', sa.Column('product_url', sa.String(length=2048), nullable=True))
    op.add_column('reels', sa.Column('product_name', sa.String(length=500), nullable=True))
    op.add_column('reels', sa.Column('category_id', sa.Integer(), nullable=True))
    op.add_column('reels', sa.Column('category_name', sa.String(length=255), nullable=True))
    op.add_column('reels', sa.Column('platform', sa.String(length=50), nullable=True))

    # FK for category_id
    op.create_foreign_key(
        'fk_reels_category_id',
        'reels', 'categories',
        ['category_id'], ['category_id'],
    )

    # Make product_id nullable
    op.alter_column(
        'reels',
        'product_id',
        existing_type=sa.Integer(),
        nullable=True,
    )

    # Index on platform for feed/visibility
    op.create_index('idx_reels_platform', 'reels', ['platform'])

    # Backfill: existing reels are AOIN; set platform and product_url
    import os
    base_url = os.getenv('PRODUCT_PAGE_BASE_URL', os.getenv('FRONTEND_URL', 'https://aoinstore.com'))
    if base_url:
        base_url = base_url.rstrip('/')
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE reels SET platform = 'aoin', product_url = CONCAT(:base, '/product/', product_id) WHERE product_id IS NOT NULL"
        ).bindparams(base=base_url or '')
    )


def downgrade():
    op.drop_index('idx_reels_platform', table_name='reels')
    op.alter_column(
        'reels',
        'product_id',
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_constraint('fk_reels_category_id', 'reels', type_='foreignkey')
    op.drop_column('reels', 'platform')
    op.drop_column('reels', 'category_name')
    op.drop_column('reels', 'category_id')
    op.drop_column('reels', 'product_name')
    op.drop_column('reels', 'product_url')
