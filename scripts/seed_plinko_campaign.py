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

# Artwork for the panel beside the game. A single entry is rendered whole, which is
# what a finished poster like this one needs — it carries its own headline, offer badge
# and call to action, and tiling it into a grid would crop that copy off. Supply two to
# four plain photographs instead if you want the grid.
#
# Swap this in Superadmin -> Plinko Campaigns; it lives here only so a fresh install
# is not empty on day one.
DEFAULT_IMAGES = [
    "https://d34ykwjwy6y000.cloudfront.net/assets/carousel/"
    "4922e3ab-d9f7-47c9-83c0-bf92569013e5_ChatGPT_Image_Aug_11_2026_11_50_34_AM.png",
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
        # Backfill artwork only when there is none. A campaign seeded before
        # image_urls existed would otherwise keep showing the blank fallback panel
        # forever, with no obvious reason why. Anything already configured is left
        # alone — this fills a gap, it does not overwrite an admin's choice.
        if not existing.get_image_urls():
            existing.image_urls = json.dumps(DEFAULT_IMAGES)
            db.session.commit()
            print(f"✓ Campaign '{CAMPAIGN_NAME}' (id={existing.campaign_id}) had no artwork; added the default poster.")
        else:
            print(f"✓ Campaign '{CAMPAIGN_NAME}' already exists (id={existing.campaign_id}) with artwork; nothing to do.")
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
