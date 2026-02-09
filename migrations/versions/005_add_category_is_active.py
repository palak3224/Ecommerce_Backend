"""add is_active to categories

Revision ID: 005_add_category_is_active
Revises: 004_add_username
Create Date: 2025-02-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '005_add_category_is_active'
down_revision = '004_add_username'
branch_labels = None
depends_on = None


def upgrade():
    """Add is_active column to categories table (default True for existing rows)."""
    op.add_column(
        'categories',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true())
    )


def downgrade():
    """Remove is_active column from categories table."""
    op.drop_column('categories', 'is_active')
