"""add username to merchant_profiles

Revision ID: 004_add_username
Revises: 002_add_dob_gender
Create Date: 2025-01-05 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_username'
down_revision = '002_add_dob_gender'
branch_labels = None
depends_on = None


def upgrade():
    """Add username, username_updated_at, and profile_img columns to merchant_profiles table."""
    op.add_column('merchant_profiles', sa.Column('username', sa.String(50), nullable=True))
    op.add_column('merchant_profiles', sa.Column('username_updated_at', sa.DateTime(), nullable=True))
    op.add_column('merchant_profiles', sa.Column('profile_img', sa.String(512), nullable=True))
    op.create_index('ix_merchant_profiles_username', 'merchant_profiles', ['username'], unique=True)


def downgrade():
    """Remove username, username_updated_at, and profile_img columns from merchant_profiles table."""
    op.drop_index('ix_merchant_profiles_username', 'merchant_profiles')
    op.drop_column('merchant_profiles', 'profile_img')
    op.drop_column('merchant_profiles', 'username_updated_at')
    op.drop_column('merchant_profiles', 'username')

