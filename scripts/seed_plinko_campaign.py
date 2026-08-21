"""
Seed a default "Tap to drop" lead-capture campaign so the homepage popup has
something to serve. Without an active campaign GET /api/plinko/campaign returns
{"active": false} and the popup never opens.

The board mirrors the reference layout: five slots, two of them decoys. Decoys are
drawn on the board but excluded from the weighted draw, which is what lets the game
promise that everyone wins while still looking like a game of chance.

Default odds (coupon slots only):
    15% back ->  10/100 = 10%
    10% back ->  30/100 = 30%
     5% back ->  60/100 = 60%

Guardrails are deliberately conservative: minimum order 999, discount capped at 500,
valid the same day only, and at most 500 codes minted per day — so worst-case daily
exposure is bounded at 500 x 500 before anyone has to notice. Tune all of it from
Superadmin -> Plinko Campaigns.

Idempotent: does nothing if a campaign with the same name already exists.

Usage:
    python scripts/seed_plinko_campaign.py
"""

import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from common.database import db
from models.plinko import PlinkoCampaign, PlinkoPrize

CAMPAIGN_NAME = "Tap to Drop — Launch"

# The four images beside the game. These ship as a sensible default so the popup is
# not empty on day one; swap them for real campaign artwork in
# Superadmin -> Plinko Campaigns, which is why they are data and not hardcoded.
DEFAULT_IMAGES = [
    "/assets/images/similar1.jpg",
    "/assets/images/similar2.jpg",
    "/assets/images/similar3.jpg",
    "/assets/images/similar4.jpg",
]

SLOTS = [
    # (label,      slot_kind, discount_type, value, weight, order)
    ("15% back",   "coupon",  "percentage",  "15",  10,     0),
    ("Try again",  "decoy",   None,          None,   0,     1),
    ("Free gift",  "decoy",   None,          None,   0,     2),
    ("10% back",   "coupon",  "percentage",  "10",  30,     3),
    ("5% back",    "coupon",  "percentage",  "5",   60,     4),
]


def seed():
    existing = PlinkoCampaign.query.filter_by(name=CAMPAIGN_NAME).first()
    if existing:
        print(f"✓ Campaign '{CAMPAIGN_NAME}' already exists (id={existing.campaign_id}); nothing to do.")
        return

    campaign = PlinkoCampaign(
        name=CAMPAIGN_NAME,
        is_active=True,
        headline="Tap to drop",
        subheadline="Play once — every drop wins a discount.",
        terms_text=(
            "Valid on a single order placed today only. Minimum order value ₹999. "
            "Maximum discount ₹500. One code per customer. Cannot be combined with "
            "other offers."
        ),
        coupon_prefix="PLK",
        validity_days=1,
        min_order_value=Decimal("999.00"),
        max_discount_amount=Decimal("500.00"),
        popup_delay_seconds=5,
        redisplay_after_days=7,
        daily_mint_ceiling=500,
        image_urls=json.dumps(DEFAULT_IMAGES),
    )
    db.session.add(campaign)
    db.session.flush()

    # Only one campaign may be live at a time; the storefront asks for "the" active one.
    PlinkoCampaign.query.filter(
        PlinkoCampaign.campaign_id != campaign.campaign_id
    ).update({PlinkoCampaign.is_active: False}, synchronize_session=False)

    for label, kind, dtype, value, weight, order in SLOTS:
        db.session.add(PlinkoPrize(
            campaign_id=campaign.campaign_id,
            label=label,
            slot_kind=kind,
            discount_type=dtype,
            discount_value=Decimal(value) if value else None,
            weight=weight,
            display_order=order,
            is_active=True,
        ))

    db.session.commit()
    print(f"✓ Seeded campaign '{CAMPAIGN_NAME}' (id={campaign.campaign_id}) with {len(SLOTS)} slots.")
    print("  It is now live. Visit the homepage and wait 5 seconds.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed()
