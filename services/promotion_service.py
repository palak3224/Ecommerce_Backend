# FILE: services/promotion_service.py
"""The one place a promo code is judged valid.

Two endpoints price a promo code: POST /api/promo-code/apply (display) and
POST /api/checkout/quote (authoritative). checkout_quote_service's docstring insists the
two must not drift, because a disagreement either overcharges the customer or hands them
free money. Adding rules in two places guarantees drift, so every rule lives here and
both call it.

This is a *leaf* module on purpose: it imports no routes and not checkout_quote_service,
which already has a documented import cycle with routes.razorpay_routes. A display-only
endpoint should not have to drag fx_service and razorpay in behind it.

business_today() exists because the two callers disagreed about what day it is:
promo_code_routes used date.today() (server-local) while checkout_quote_service used
datetime.utcnow().date() (UTC). On an IST box those differ between 00:00 and 05:30, so a
same-day coupon minted at 01:00 IST would be advertised as valid and then silently
produce no discount at checkout. Minting, display and pricing must all read one clock.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

import pytz
from flask import current_app

from models.promotion import Promotion
from models.promotion_redemption import PromotionRedemption


DEFAULT_PROMO_TIMEZONE = "Asia/Kolkata"

# reason_code values. None means valid.
NOT_FOUND = "NOT_FOUND"
INACTIVE = "INACTIVE"
NOT_STARTED = "NOT_STARTED"
EXPIRED = "EXPIRED"
ALREADY_USED = "ALREADY_USED"
BELOW_MIN_ORDER = "BELOW_MIN_ORDER"
NOT_YOURS = "NOT_YOURS"

# Rejections the checkout quote should surface loudly rather than swallow. A code the
# customer explicitly typed that fails for a reason they can act on ("spend 200 more")
# must not vanish into "no discount, no explanation".
LOUD_REASONS = frozenset({ALREADY_USED, BELOW_MIN_ORDER, NOT_YOURS})


def business_today(now=None) -> date:
    """The calendar date the business is operating in. One clock for every promo check.

    `now` is treated as naive UTC when given (matching datetime.utcnow() elsewhere in
    this codebase) and converted into PROMO_TIMEZONE before the date is taken.
    """
    tz_name = current_app.config.get("PROMO_TIMEZONE", DEFAULT_PROMO_TIMEZONE)
    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        current_app.logger.warning(
            "Unknown PROMO_TIMEZONE %r, falling back to %s", tz_name, DEFAULT_PROMO_TIMEZONE
        )
        tz = pytz.timezone(DEFAULT_PROMO_TIMEZONE)

    if now is None:
        moment = pytz.utc.localize(datetime.utcnow())
    elif now.tzinfo is None:
        moment = pytz.utc.localize(now)
    else:
        moment = now
    return moment.astimezone(tz).date()


@dataclass(frozen=True)
class PromotionResolution:
    """The verdict on one code. `ok` means spend it; otherwise reason_code says why not.

    A result object rather than an exception because the two callers need *different*
    behaviour for the same fact, and both behaviours are contractual:
    /api/promo-code/apply distinguishes 404 from 400, while the quote stays silent for
    an unknown or expired code (tests/test_checkout_quote.py asserts exactly that).
    """

    promotion: Optional[Promotion] = None
    reason_code: Optional[str] = None
    message: Optional[str] = None
    http_status: Optional[int] = None

    @property
    def ok(self) -> bool:
        return self.reason_code is None and self.promotion is not None

    @property
    def is_loud(self) -> bool:
        """True when the caller should tell the customer, not silently drop the discount."""
        return self.reason_code in LOUD_REASONS


def _reject(reason_code, message, http_status=400):
    return PromotionResolution(
        promotion=None, reason_code=reason_code, message=message, http_status=http_status
    )


def _money(value):
    return Decimal(str(value))


def resolve_promotion(code, *, now=None, user=None, basket_total_inclusive=None):
    """Look up a promo code and judge it. Never trusts a client-supplied amount.

    `basket_total_inclusive` is the pre-discount, tax-inclusive, pre-shipping basket
    total — the figure the customer sees on the cart page, so an advertised
    "min order 2000" means what it says. Passing None skips the minimum check, which is
    correct only for callers that have no basket yet.
    """
    if not code:
        return _reject(NOT_FOUND, "Invalid promotion code.", 404)

    normalised = str(code).strip().upper()
    promo = Promotion.query.filter(
        Promotion.code == normalised,
        Promotion.deleted_at.is_(None),
    ).first()
    if not promo:
        return _reject(NOT_FOUND, "Invalid promotion code.", 404)

    if not promo.active_flag:
        return _reject(INACTIVE, "This promotion is currently inactive.")

    today = business_today(now)
    if promo.start_date and today < promo.start_date:
        return _reject(NOT_STARTED, "This promotion is not yet active.")
    if promo.end_date and today > promo.end_date:
        return _reject(EXPIRED, "This promotion has expired.")

    # Single-use: a redemption row exists iff the code has been spent on an order.
    if PromotionRedemption.query.filter_by(promotion_id=promo.promotion_id).first():
        return _reject(ALREADY_USED, "This promo code has already been used.")

    # Email binding is recorded on every minted code but enforced only when the flag is
    # on. Rejecting a legitimate winner who signed up with a different address costs
    # more (an invisible churned customer) than a leaked single-use, capped, one-day
    # code does. Log the mismatch either way so the decision can be made on numbers.
    if promo.restricted_to_email:
        holder = (getattr(user, "email", None) or "").strip().lower()
        owner = promo.restricted_to_email.strip().lower()
        if holder != owner:
            if current_app.config.get("PROMO_EMAIL_BINDING_ENFORCED", False):
                return _reject(NOT_YOURS, "This promo code was issued to a different account.")
            current_app.logger.warning(
                "Promo %s issued to %s used by %s (binding not enforced)",
                promo.code, owner, holder or "<anonymous>",
            )

    if promo.min_order_value is not None and basket_total_inclusive is not None:
        minimum = _money(promo.min_order_value)
        if _money(basket_total_inclusive) < minimum:
            return _reject(
                BELOW_MIN_ORDER,
                f"This code needs a minimum order of {minimum:.2f}.",
            )

    return PromotionResolution(promotion=promo)


def discount_cap_for(promo):
    """The promo's max discount as a non-negative Decimal, or None when uncapped."""
    if promo is None or promo.max_discount_amount is None:
        return None
    return max(_money(promo.max_discount_amount), Decimal("0"))
