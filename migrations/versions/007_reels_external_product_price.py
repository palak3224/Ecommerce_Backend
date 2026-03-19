"""reels external product price

Revision ID: 007_reels_external_price
Revises: 006_reels_aoin_external
Create Date: 2025-03-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '007_reels_external_price'
down_revision = '006_reels_aoin_external'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'reels',
        sa.Column('external_product_price', sa.Numeric(12, 2), nullable=True)
    )


def downgrade():
    op.drop_column('reels', 'external_product_price')
