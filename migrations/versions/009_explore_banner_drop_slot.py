"""drop slot column from explore_banners (banners are now a carousel)

Revision ID: 009_explore_banner_drop_slot
Revises: 008_add_explore_banners
Create Date: 2026-07-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '009_explore_banner_drop_slot'
down_revision = '008_add_explore_banners'
branch_labels = None
depends_on = None


def upgrade():
    """Explore banners are a free 1-3 carousel ordered by display_order; the
    fixed named slot is no longer used."""
    with op.batch_alter_table('explore_banners') as batch_op:
        batch_op.drop_column('slot')


def downgrade():
    with op.batch_alter_table('explore_banners') as batch_op:
        batch_op.add_column(sa.Column('slot', sa.String(length=20), nullable=True))
