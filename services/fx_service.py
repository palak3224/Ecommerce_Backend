# services/fx_service.py
"""Currency conversion.

**This module never invents a rate.** If it cannot find a usable one it raises. The
tempting `rate = lookup(...) or 1` is how an $85 item becomes an Rs 85 sale, and the
frontend already shipped that exact bug once (OrderSummary.tsx did
`exchangeRates[currency] || 1`, printing rupee figures under a dollar sign).

Everything is Decimal. A float rate of 0.0105016627 multiplied by a basket total
lands somewhere near the right answer, and "near" is not a thing money does.

Conversion is display-only. INR remains the book currency (docs/MULTI_CURRENCY.md
section 3): nothing here writes to an order, and no read path re-converts a
historical order (I12).
"""
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP

from flask import current_app

from common.database import db
from models.fx_rate import FxRate


class FxError(Exception):
    """Base for every reason a conversion could not be made."""


class NoFxRateError(FxError):
    """No rate exists for this pair at all."""


class StaleFxRateError(FxError):
    """A rate exists but is too old to charge or quote against."""


def _max_age_days():
    return int(current_app.config.get("FX_MAX_RATE_AGE_DAYS", 3))


def _markup_percent():
    """Spread added on top of the mid-market rate.

    Covers the gap between the reference rate and what the gateway actually settles
    at. Kept in config because it is a commercial decision, not a technical one.
    """
    return Decimal(str(current_app.config.get("FX_MARKUP_PERCENT", "0")))


def get_rate_row(base, quote, on_date=None):
    """The most recent usable FxRate row for a pair, or raise.

    Returns the row rather than the number so callers can record `fx_rate_id` and
    prove later exactly which rate an order was priced at (I4).
    """
    base = (base or "").upper()
    quote = (quote or "").upper()

    if base == quote:
        # The one case where 1.0 is genuinely correct, and it is not a fallback:
        # converting a currency to itself. No row is needed or invented.
        return None

    on_date = on_date or date.today()
    row = (
        FxRate.query.filter(
            FxRate.base_currency == base,
            FxRate.quote_currency == quote,
            FxRate.as_of_date <= on_date,
        )
        .order_by(FxRate.as_of_date.desc(), FxRate.fx_rate_id.desc())
        .first()
    )

    if row is None:
        raise NoFxRateError(f"No {base}->{quote} rate on or before {on_date}.")

    age = (on_date - row.as_of_date).days
    if age > _max_age_days():
        raise StaleFxRateError(
            f"Newest {base}->{quote} rate is {row.as_of_date} ({age} days old); "
            f"the limit is {_max_age_days()}."
        )
    return row


def get_rate(base, quote, on_date=None):
    """The Decimal rate for a pair. Raises rather than guessing."""
    if (base or "").upper() == (quote or "").upper():
        return Decimal("1")
    return Decimal(get_rate_row(base, quote, on_date).rate)


def convert(amount, base, quote, on_date=None, apply_markup=True):
    """Convert a Decimal amount between currencies. Raises if no usable rate.

    There is deliberately no `default=` parameter. A caller that wants a fallback
    has to write it themselves, in the open, where a reviewer can see it.
    """
    amount = Decimal(str(amount))
    base_u, quote_u = (base or "").upper(), (quote or "").upper()
    if base_u == quote_u:
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    rate = get_rate(base_u, quote_u, on_date)
    converted = amount * rate

    if apply_markup:
        markup = _markup_percent()
        if markup:
            converted = converted * (Decimal("1") + markup / Decimal("100"))

    return converted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def apply_marketing_rounding(amount, currency):
    """Nudge a converted price to something that looks priced rather than computed.

    15.5921 -> 15.99. Always rounds UP to the charm point, never down: rounding a
    derived price down would sell below the INR list price once the markup is gone.
    Rows with a merchant-set override skip this entirely.
    """
    amount = Decimal(str(amount))
    style = (current_app.config.get("FX_ROUNDING_STYLE") or "charm_99").lower()

    if style == "none":
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if style == "integer":
        return amount.quantize(Decimal("1"), rounding=ROUND_UP)

    # charm_99: round up to the next whole unit, then step back one minor unit.
    whole = amount.quantize(Decimal("1"), rounding=ROUND_UP)
    charmed = whole - Decimal("0.01")
    if charmed < amount:
        # amount was already at or above the charm point for this whole unit.
        charmed = whole + Decimal("0.99")
    return charmed.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def to_presentment(amount_base, quote_currency, base_currency=None, on_date=None,
                   marketing_rounding=True):
    """Price an INR amount in a presentment currency.

    Returns (Decimal amount, FxRate row or None). The row is the audit trail — store
    its id alongside any amount you persist.
    """
    base_currency = base_currency or current_app.config.get("DEFAULT_CURRENCY", "INR")
    if (quote_currency or "").upper() == base_currency.upper():
        return Decimal(str(amount_base)).quantize(Decimal("0.01")), None

    row = get_rate_row(base_currency, quote_currency, on_date)
    converted = convert(amount_base, base_currency, quote_currency, on_date)
    if marketing_rounding:
        converted = apply_marketing_rounding(converted, quote_currency)
    return converted, row


def record_rate(base, quote, rate, as_of, source):
    """Append one rate. Idempotent per (pair, day, source) — never updates.

    Returns the row, existing or new. A job that runs twice in a day is a no-op the
    second time rather than a second competing answer.
    """
    base, quote = base.upper(), quote.upper()
    existing = FxRate.query.filter_by(
        base_currency=base, quote_currency=quote, as_of_date=as_of, source=source
    ).first()
    if existing:
        return existing

    row = FxRate(
        base_currency=base,
        quote_currency=quote,
        rate=Decimal(str(rate)),
        as_of_date=as_of,
        source=source,
        fetched_at=datetime.utcnow(),
    )
    db.session.add(row)
    db.session.commit()
    return row


def snapshot_rates_from_provider():
    """Fetch today's rates and append them. Returns how many rows were written.

    Used by the daily job. Network failure is logged and swallowed — a missed
    snapshot leaves yesterday's rate in place, which `get_rate_row` will keep
    serving until it goes stale and then refuse. That is the intended behaviour:
    degrade to refusing, never to guessing.
    """
    import requests

    api_key = current_app.config.get("FREECURRENCY_API_KEY")
    if not api_key:
        current_app.logger.error("FX snapshot skipped: FREECURRENCY_API_KEY not set")
        return 0

    base = current_app.config.get("DEFAULT_CURRENCY", "INR")
    wanted = [c.strip().upper() for c in
              (current_app.config.get("FX_QUOTE_CURRENCIES") or "USD").split(",")
              if c.strip()]

    try:
        resp = requests.get(
            "https://api.freecurrencyapi.com/v1/latest",
            params={"apikey": api_key, "base_currency": base,
                    "currencies": ",".join(wanted)},
            headers={"Accept": "application/json"},
            timeout=15,
        )
    except Exception as e:
        current_app.logger.error("FX snapshot request failed: %s", e)
        return 0

    if resp.status_code != 200:
        current_app.logger.error(
            "FX snapshot provider returned %s: %s", resp.status_code, resp.text[:300]
        )
        return 0

    try:
        payload = resp.json()["data"]
    except Exception as e:
        current_app.logger.error("FX snapshot payload unreadable: %s", e)
        return 0

    today = date.today()
    written = 0
    for quote in wanted:
        value = payload.get(quote)
        if value is None:
            current_app.logger.warning("FX snapshot: provider omitted %s", quote)
            continue
        # str(value) via Decimal, never float(value) — the provider sends a JSON
        # number that json already parsed to float, so re-serialise it as text
        # before it reaches the database.
        record_rate(base, quote, Decimal(str(value)), today, "freecurrencyapi")
        written += 1

    current_app.logger.info("FX snapshot wrote %s rate(s) for %s", written, today)
    return written
