"""create brand categories table

Revision ID: create_brand_categories
Revises: 
Create Date: 2024-03-19

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'create_brand_categories'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create brand_categories table
    op.create_table(
        'brand_categories',
        sa.Column('brand_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow),
        sa.ForeignKeyConstraint(['brand_id'], ['brands.brand_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.category_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('brand_id', 'category_id')
    )

    # Create index for better query performance
    op.create_index(
        'ix_brand_categories_brand_id',
        'brand_categories',
        ['brand_id']
    )
    op.create_index(
        'ix_brand_categories_category_id',
        'brand_categories',
        ['category_id']
    )

def downgrade():
    # Drop indexes
    op.drop_index('ix_brand_categories_category_id')
    op.drop_index('ix_brand_categories_brand_id')
    
    # Drop table
    op.drop_table('brand_categories') 