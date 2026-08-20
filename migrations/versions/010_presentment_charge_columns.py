"""add presentment (USD charge) snapshot columns to checkout_quotes and orders

Phase 7 — charge international customers in USD while INR stays the book currency.
Every column here is nullable with NO server default: INR checkouts and all historical
rows must leave them empty (docs/MULTI_CURRENCY.md Landmine #1). `fx_rate_id` is a
plain reference id into the append-only fx_rates table, not a DB foreign key.

Revision ID: 010_presentment_charge_columns
Revises: 009_explore_banner_drop_slot
Create Date: 2026-07-29 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '010_presentment_charge_columns'
down_revision = '009_explore_banner_drop_slot'
branch_labels = None
depends_on = None


_PRESENTMENT_COLUMNS = [
    ('presentment_currency', sa.String(length=3)),
    ('presentment_subtotal_amount', sa.Numeric(12, 2)),
    ('presentment_discount_amount', sa.Numeric(12, 2)),
    ('presentment_tax_amount', sa.Numeric(12, 2)),
    ('presentment_shipping_amount', sa.Numeric(12, 2)),
    ('presentment_total_amount', sa.Numeric(12, 2)),
    ('presentment_total_minor', sa.BigInteger()),
    ('fx_rate_id', sa.Integer()),
]


def upgrade():
    for table in ('checkout_quotes', 'orders'):
        with op.batch_alter_table(table) as batch_op:
            for name, coltype in _PRESENTMENT_COLUMNS:
                batch_op.add_column(sa.Column(name, coltype, nullable=True))


def downgrade():
    for table in ('checkout_quotes', 'orders'):
        with op.batch_alter_table(table) as batch_op:
            for name, _ in reversed(_PRESENTMENT_COLUMNS):
                batch_op.drop_column(name)
