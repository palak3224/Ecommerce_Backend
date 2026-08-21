# FILE: models/plinko.py
"""Tables behind the storefront lead-capture game.

Three tables, deliberately separate from GamePlay: game_plays.user_id is NOT NULL and
every /api/games/* route is JWT-gated, so that engine cannot serve the anonymous
visitor this feature exists to capture.

The important shape here is that a *lead* is not a *coupon*. A visitor who plays and
walks away leaves a plinko_leads row and nothing else; the promotions table only grows
when someone completes the funnel. That keeps "how many played" and "how many cost us
money" as separate, honest numbers.
"""
from datetime import datetime

from common.database import db


class PlinkoCampaign(db.Model):
    """One configured run of the game. Only one should be active at a time."""

    __tablename__ = 'plinko_campaigns'

    campaign_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=False, index=True)

    headline = db.Column(db.String(200), nullable=False, default='Tap to drop')
    subheadline = db.Column(db.String(300), nullable=True)
    # Shown next to the revealed code. This is the "terms and conditions of that
    # particular day's order" the campaign promises, so it is per-campaign copy rather
    # than a hardcoded string.
    terms_text = db.Column(db.Text, nullable=True)

    coupon_prefix = db.Column(db.String(12), nullable=False, default='PLK')
    # 1 = valid for today only.
    validity_days = db.Column(db.Integer, nullable=False, default=1)
    min_order_value = db.Column(db.Numeric(10, 2), nullable=True)
    max_discount_amount = db.Column(db.Numeric(10, 2), nullable=True)

    popup_delay_seconds = db.Column(db.Integer, nullable=False, default=5)
    redisplay_after_days = db.Column(db.Integer, nullable=False, default=7)
    # The circuit breaker. Worst-case daily liability is this x max_discount_amount,
    # which is a number that can be agreed in advance rather than discovered.
    daily_mint_ceiling = db.Column(db.Integer, nullable=False, default=500)

    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    prizes = db.relationship(
        'PlinkoPrize', backref='campaign', order_by='PlinkoPrize.display_order'
    )

    def serialize(self, include_weights=False):
        data = {
            'campaign_id': self.campaign_id,
            'name': self.name,
            'is_active': self.is_active,
            'headline': self.headline,
            'subheadline': self.subheadline,
            'terms_text': self.terms_text,
            'coupon_prefix': self.coupon_prefix,
            'validity_days': self.validity_days,
            'min_order_value': float(self.min_order_value) if self.min_order_value is not None else None,
            'max_discount_amount': float(self.max_discount_amount) if self.max_discount_amount is not None else None,
            'popup_delay_seconds': self.popup_delay_seconds,
            'redisplay_after_days': self.redisplay_after_days,
            'daily_mint_ceiling': self.daily_mint_ceiling,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'prizes': [p.serialize(include_weights=include_weights)
                       for p in self.prizes if p.is_active],
        }
        return data


class PlinkoPrize(db.Model):
    """A slot on the board.

    slot_kind='decoy' is how "Try again" and "Free gift" appear in the prize strip
    without ever being winnable — they are drawn but excluded from the draw. Only
    'coupon' slots with weight > 0 can be selected, which is what makes "everyone wins"
    true no matter how the board is decorated.
    """

    __tablename__ = 'plinko_prizes'

    prize_id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(
        db.Integer, db.ForeignKey('plinko_campaigns.campaign_id'), nullable=False, index=True
    )
    label = db.Column(db.String(60), nullable=False)
    # 'coupon' | 'decoy'. String, not Enum: init_db's auto-migration only ever ADDs
    # columns, so an Enum that later gains a value needs hand-written DDL.
    slot_kind = db.Column(db.String(16), nullable=False, default='coupon')
    # 'percentage' | 'fixed', mirroring models.enums.DiscountType values.
    discount_type = db.Column(db.String(16), nullable=True)
    discount_value = db.Column(db.Numeric(10, 2), nullable=True)
    weight = db.Column(db.Integer, nullable=False, default=1)
    display_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    def serialize(self, include_weights=False):
        data = {
            'prize_id': self.prize_id,
            'label': self.label,
            'slot_kind': self.slot_kind,
            'display_order': self.display_order,
        }
        if include_weights:
            # Weights are admin-only. Shipping them to the storefront would tell a
            # visitor exactly how the draw is rigged.
            data.update({
                'discount_type': self.discount_type,
                'discount_value': float(self.discount_value) if self.discount_value is not None else None,
                'weight': self.weight,
                'is_active': self.is_active,
            })
        return data


class PlinkoLead(db.Model):
    """One visitor's progress through play -> email -> phone."""

    __tablename__ = 'plinko_leads'

    lead_id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(
        db.Integer, db.ForeignKey('plinko_campaigns.campaign_id'), nullable=False, index=True
    )
    prize_id = db.Column(db.Integer, db.ForeignKey('plinko_prizes.prize_id'), nullable=True)
    promotion_id = db.Column(db.Integer, nullable=True, index=True)

    session_token = db.Column(db.String(64), nullable=False, unique=True, index=True)
    # The code is generated at play time and held here, so the reveal can hand back
    # half of a real string without a promotions row existing yet.
    pending_code = db.Column(db.String(50), nullable=True)

    email = db.Column(db.String(255), nullable=True, index=True)
    phone = db.Column(db.String(20), nullable=True, index=True)
    # Set only on completion, and UNIQUE. MySQL and SQLite both allow duplicate NULLs,
    # so half-finished leads are unconstrained while completed ones are deduped by the
    # database rather than by an application check that loses the race.
    claimed_email = db.Column(db.String(255), nullable=True, unique=True)
    claimed_phone = db.Column(db.String(20), nullable=True, unique=True)

    # 'played' -> 'email_captured' -> 'completed'
    status = db.Column(db.String(20), nullable=False, default='played', index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    source_page = db.Column(db.String(255), nullable=True)
    # Hashed, not raw: this is abuse plumbing, not a reason to store visitor IPs.
    ip_hash = db.Column(db.String(64), nullable=True, index=True)
    user_agent = db.Column(db.String(255), nullable=True)

    expires_at = db.Column(db.DateTime, nullable=True)
    coupon_revealed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    prize = db.relationship('PlinkoPrize')

    __table_args__ = (
        db.Index('idx_plinko_leads_ip_created', 'ip_hash', 'created_at'),
    )

    def serialize(self):
        return {
            'lead_id': self.lead_id,
            'campaign_id': self.campaign_id,
            'prize_label': self.prize.label if self.prize else None,
            'promotion_id': self.promotion_id,
            'email': self.email,
            'phone': self.phone,
            'status': self.status,
            'source_page': self.source_page,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'coupon_revealed_at': self.coupon_revealed_at.isoformat() if self.coupon_revealed_at else None,
        }
