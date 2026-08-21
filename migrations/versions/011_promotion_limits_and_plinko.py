"""promotion redemption rules, quote/order promo snapshot, and the plinko lead tables

Two things worth knowing before touching this file.

1. This is a MERGE revision. Revisions 010_presentment_charge_columns and
   010_add_group_key_to_explore_banners both declare down_revision
   '009_explore_banner_drop_slot', so the graph has had two heads and
   `alembic upgrade head` has been failing with "Multiple head revisions are present".
   Naming both parents here closes that fork as well as adding this migration's own
   changes.

2. This repo runs `python init_db.py`, not Alembic (there is no alembic.ini and no
   migrations/env.py). A database built by init_db.py already has every column below,
   because db.create_all() reads them off the models. So each step is guarded by an
   inspector check rather than assuming a clean slate — an unguarded upgrade() would
   die on "duplicate column name".

Every new column is nullable with no server default: historical promotions must keep
reading as "no minimum, no cap, bound to nobody", which is exactly how they behaved
before these rules existed.

Revision ID: 011_promotion_limits_and_plinko
Revises: 010_presentment_charge_columns, 010_add_group_key_to_explore_banners
Create Date: 2026-08-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '011_promotion_limits_and_plinko'
down_revision = ('010_presentment_charge_columns', '010_add_group_key_to_explore_banners')
branch_labels = None
depends_on = None


_NEW_COLUMNS = {
    'promotions': [
        ('min_order_value', sa.Numeric(10, 2)),
        ('max_discount_amount', sa.Numeric(10, 2)),
        ('restricted_to_email', sa.String(length=255)),
        ('lead_id', sa.Integer()),
        ('source', sa.String(length=32)),
    ],
    'checkout_quotes': [
        ('promotion_id', sa.Integer()),
        ('promo_code', sa.String(length=50)),
    ],
    'orders': [
        ('promotion_id', sa.Integer()),
        ('promo_code', sa.String(length=50)),
    ],
}


def _existing(inspector, table):
    if table not in inspector.get_table_names():
        return None
    return {c['name'] for c in inspector.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table, columns in _NEW_COLUMNS.items():
        existing = _existing(inspector, table)
        if existing is None:
            continue
        missing = [(n, t) for n, t in columns if n not in existing]
        if not missing:
            continue
        with op.batch_alter_table(table) as batch_op:
            for name, coltype in missing:
                batch_op.add_column(sa.Column(name, coltype, nullable=True))

    tables = set(inspector.get_table_names())

    if 'promotion_redemptions' not in tables:
        op.create_table(
            'promotion_redemptions',
            sa.Column('redemption_id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('promotion_id', sa.Integer(), nullable=False),
            sa.Column('order_id', sa.String(length=50), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('quote_id', sa.String(length=64), nullable=True),
            sa.Column('lead_id', sa.Integer(), nullable=True),
            sa.Column('discount_amount', sa.Numeric(12, 2), nullable=False),
            sa.Column('redeemed_at', sa.DateTime(), nullable=False),
            # The single-use guarantee. A promotion can be spent exactly once, enforced
            # by the database rather than by a read-then-write check that loses races.
            sa.UniqueConstraint('promotion_id', name='uq_promo_redemption_promotion'),
        )

    if 'plinko_campaigns' not in tables:
        op.create_table(
            'plinko_campaigns',
            sa.Column('campaign_id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('headline', sa.String(length=200), nullable=False),
            sa.Column('subheadline', sa.String(length=300), nullable=True),
            sa.Column('terms_text', sa.Text(), nullable=True),
            sa.Column('image_urls', sa.Text(), nullable=True),
            sa.Column('coupon_prefix', sa.String(length=12), nullable=False, server_default='PLK'),
            sa.Column('validity_days', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('min_order_value', sa.Numeric(10, 2), nullable=True),
            sa.Column('max_discount_amount', sa.Numeric(10, 2), nullable=True),
            sa.Column('popup_delay_seconds', sa.Integer(), nullable=False, server_default='5'),
            sa.Column('redisplay_after_days', sa.Integer(), nullable=False, server_default='7'),
            sa.Column('daily_mint_ceiling', sa.Integer(), nullable=False, server_default='500'),
            sa.Column('start_date', sa.Date(), nullable=True),
            sa.Column('end_date', sa.Date(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
        )

    if 'plinko_prizes' not in tables:
        op.create_table(
            'plinko_prizes',
            sa.Column('prize_id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('campaign_id', sa.Integer(), nullable=False),
            sa.Column('label', sa.String(length=60), nullable=False),
            sa.Column('slot_kind', sa.String(length=16), nullable=False, server_default='coupon'),
            sa.Column('discount_type', sa.String(length=16), nullable=True),
            sa.Column('discount_value', sa.Numeric(10, 2), nullable=True),
            sa.Column('weight', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        )

    if 'plinko_leads' not in tables:
        op.create_table(
            'plinko_leads',
            sa.Column('lead_id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('campaign_id', sa.Integer(), nullable=False),
            sa.Column('prize_id', sa.Integer(), nullable=True),
            sa.Column('promotion_id', sa.Integer(), nullable=True),
            sa.Column('session_token', sa.String(length=64), nullable=False, unique=True),
            sa.Column('pending_code', sa.String(length=50), nullable=True),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('phone', sa.String(length=20), nullable=True),
            # Unique, and NULL until the lead completes — both MySQL and SQLite permit
            # duplicate NULLs, so abandoned leads stay unconstrained.
            sa.Column('claimed_email', sa.String(length=255), nullable=True, unique=True),
            sa.Column('claimed_phone', sa.String(length=20), nullable=True, unique=True),
            sa.Column('status', sa.String(length=20), nullable=False, server_default='played'),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('source_page', sa.String(length=255), nullable=True),
            sa.Column('ip_hash', sa.String(length=64), nullable=True),
            sa.Column('user_agent', sa.String(length=255), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('coupon_revealed_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
        )
        op.create_index('idx_plinko_leads_ip_created', 'plinko_leads', ['ip_hash', 'created_at'])


def downgrade():
    op.drop_index('idx_plinko_leads_ip_created', table_name='plinko_leads')
    for table in ('plinko_leads', 'plinko_prizes', 'plinko_campaigns', 'promotion_redemptions'):
        op.drop_table(table)
    for table, columns in _NEW_COLUMNS.items():
        with op.batch_alter_table(table) as batch_op:
            for name, _ in reversed(columns):
                batch_op.drop_column(name)
