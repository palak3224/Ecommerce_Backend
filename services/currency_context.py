# services/currency_context.py
"""Which currency is this response in, and what does a price look like in it.

Phase 3 of docs/MULTI_CURRENCY.md. Two rules make this safe to add to serializers
that ~150 frontend call sites already depend on:

1. **The query-param gate.** Presentment differs from INR *only* when the caller
   opts in with `?currency=USD` and the feature flag is on. A request without it
   gets byte-identical JSON to before. That is what makes it safe to change the
   meaning of existing scalar keys at all.

2. **Parallel scalars, not objects.** `selling_price` stays a bare number so the
   arithmetic those call sites do keeps working; `selling_price_inr` is added
   alongside and is always INR. Replacing `price: 1299` with
   `price: {amount: ...}` would break every one of them in a single deploy with no
   incremental path.

Outside a request context — background jobs, invoice PDF rendering — this always
resolves to the base currency. An invoice is a tax document and must never render
in a presentment currency by accident.
"""
import re

from flask import current_app, has_request_context, request

_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")

# Price provenance, surfaced so the frontend can tell a real price from a converted
# one and so support can explain a number a customer is querying.
SOURCE_BASE = "BASE"                 # the INR price itself, no conversion
SOURCE_DERIVED = "DERIVED"           # converted from INR at a stored rate
SOURCE_MERCHANT_OVERRIDE = "MERCHANT_OVERRIDE"   # merchant typed this price


def base_currency():
    try:
        return (current_app.config.get("DEFAULT_CURRENCY") or "INR").upper()
    except RuntimeError:
        return "INR"


def multi_currency_enabled():
    try:
        return bool(current_app.config.get("FEATURE_MULTI_CURRENCY", False))
    except RuntimeError:
        return False


def supported_currencies():
    """Base plus whatever we hold rates for."""
    try:
        quotes = (current_app.config.get("FX_QUOTE_CURRENCIES") or "USD").split(",")
    except RuntimeError:
        quotes = ["USD"]
    out = [base_currency()] + [q.strip().upper() for q in quotes if q.strip()]
    seen, unique = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def resolve_request_currency(explicit=None):
    """The currency this response should be priced in.

    Order: an explicit argument, then `?currency=`, then the base currency. An
    unknown or malformed code resolves to base rather than raising — a bad query
    param should not turn a product listing into a 400.
    """
    candidate = explicit

    if candidate is None and has_request_context():
        candidate = request.args.get("currency")

    if not candidate:
        return base_currency()

    candidate = str(candidate).strip().upper()
    if not _CURRENCY_CODE.match(candidate):
        return base_currency()
    if candidate == base_currency():
        return base_currency()

    # The gate. With the flag off, every caller gets base currency no matter what
    # they ask for, so the read path is inert until it is deliberately switched on.
    if not multi_currency_enabled():
        return base_currency()

    if candidate not in supported_currencies():
        return base_currency()

    return candidate


def money(amount_base, currency=None, override_amount=None):
    """Price one INR amount in `currency`.

    Returns a dict shaped like the Phase 3 contract, or None if `amount_base` is
    None. Amounts are **strings** (invariant I9) — a float here is how 15.99
    becomes 15.989999999999998 on the wire.

    Never raises. If no usable rate exists the price falls back to the base
    currency *and says so* via `currency`, so the caller renders a correct rupee
    price rather than a fabricated dollar one. This is the deliberate difference
    from fx_service, which raises: a listing page must still render.
    """
    if amount_base is None:
        return None

    from decimal import Decimal

    currency = (currency or base_currency()).upper()
    base = base_currency()
    amount_base = Decimal(str(amount_base)).quantize(Decimal("0.01"))

    if currency == base:
        return {
            "amount": str(amount_base),
            "currency": base,
            "amount_base": str(amount_base),
            "base_currency": base,
            "source": SOURCE_BASE,
            "fx_rate_id": None,
        }

    # A merchant-typed price for this currency wins over anything derived.
    if override_amount is not None:
        return {
            "amount": str(Decimal(str(override_amount)).quantize(Decimal("0.01"))),
            "currency": currency,
            "amount_base": str(amount_base),
            "base_currency": base,
            "source": SOURCE_MERCHANT_OVERRIDE,
            "fx_rate_id": None,
        }

    from services.fx_service import FxError, to_presentment

    try:
        converted, row = to_presentment(amount_base, currency, base_currency=base)
    except FxError as e:
        current_app.logger.warning(
            "Presentment unavailable for %s (%s); serving %s", currency, e, base
        )
        return {
            "amount": str(amount_base),
            "currency": base,
            "amount_base": str(amount_base),
            "base_currency": base,
            "source": SOURCE_BASE,
            "fx_rate_id": None,
        }

    return {
        "amount": str(converted),
        "currency": currency,
        "amount_base": str(amount_base),
        "base_currency": base,
        "source": SOURCE_DERIVED,
        "fx_rate_id": row.fx_rate_id if row else None,
    }


def scalar(price_block):
    """The bare number a legacy call site expects, from a price block."""
    if not price_block:
        return None
    return float(price_block["amount"])
