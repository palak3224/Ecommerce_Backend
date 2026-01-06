"""add date_of_birth and gender to users

Revision ID: 002_add_dob_gender
Revises: 001_create_reels
Create Date: 2025-01-05 02:26:35.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_dob_gender'
down_revision = '001_create_reels'
branch_labels = None
depends_on = None


def upgrade():
    """Add date_of_birth and gender columns to users table."""
    op.add_column('users', sa.Column('date_of_birth', sa.Date(), nullable=True))
    op.add_column('users', sa.Column('gender', sa.String(20), nullable=True))


def downgrade():
    """Remove date_of_birth and gender columns from users table."""
    op.drop_column('users', 'gender')
    op.drop_column('users', 'date_of_birth')

