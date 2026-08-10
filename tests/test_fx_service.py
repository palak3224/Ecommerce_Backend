"""Phase 2: FX rates and conversion.

docs/MULTI_CURRENCY.md calls `missing rate never returns 1.0` the single most
valuable test in the project, because a silent 1.0 fallback is how an $85 item
becomes an Rs 85 sale. That case is first below, and it is the reason this module
raises where almost every other service would return a default.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app import create_app
from common.database import db


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _rate(base="INR", quote="USD", value="0.0105", days_ago=0, source="test"):
    from services.fx_service import record_rate
    return record_rate(base, quote, Decimal(value),
                       date.today() - timedelta(days=days_ago), source)


# --------------------------------------------------------------------------- #
# the one that matters most
# --------------------------------------------------------------------------- #

def test_missing_rate_never_returns_one(app):
    """No rate must raise, never silently convert 1:1.

    If this ever returns instead of raising, an INR price is served verbatim as a
    USD price and the store sells at roughly 1/85th.
    """
    from services.fx_service import NoFxRateError, convert, get_rate

    with app.app_context():
        with pytest.raises(NoFxRateError):
            get_rate("INR", "USD")

        with pytest.raises(NoFxRateError):
            convert(Decimal("1299.00"), "INR", "USD")


def test_missing_rate_raises_for_presentment_too(app):
    """The path serializers use must fail the same way."""
    from services.fx_service import NoFxRateError, to_presentment

    with app.app_context():
        with pytest.raises(NoFxRateError):
            to_presentment(Decimal("1299.00"), "USD")


def test_stale_rate_raises_rather_than_being_used(app):
    from services.fx_service import StaleFxRateError, get_rate

    with app.app_context():
        app.config["FX_MAX_RATE_AGE_DAYS"] = 3
        _rate(days_ago=10)

        with pytest.raises(StaleFxRateError):
            get_rate("INR", "USD")


def test_fresh_rate_within_the_age_limit_is_used(app):
    from services.fx_service import get_rate

    with app.app_context():
        app.config["FX_MAX_RATE_AGE_DAYS"] = 3
        _rate(value="0.0105", days_ago=2)
        assert get_rate("INR", "USD") == Decimal("0.0105")


def test_same_currency_is_identity_without_any_row(app):
    """The only legitimate 1.0 — and it needs no rate row to exist."""
    from services.fx_service import convert, get_rate

    with app.app_context():
        assert get_rate("INR", "INR") == Decimal("1")
        assert convert(Decimal("1299.00"), "INR", "INR") == Decimal("1299.00")


# --------------------------------------------------------------------------- #
# append-only
# --------------------------------------------------------------------------- #

def test_rates_are_append_only_and_idempotent(app):
    """Recording the same pair/day/source twice must not create a second answer."""
    from models.fx_rate import FxRate

    with app.app_context():
        first = _rate(value="0.0105")
        again = _rate(value="0.0999")   # same pair/day/source, different number

        assert again.fx_rate_id == first.fx_rate_id
        assert FxRate.query.count() == 1
        # The original value stands. A correction is a new row on a new date, never
        # a mutation of a row an order may already reference (I4).
        assert Decimal(FxRate.query.first().rate) == Decimal("0.0105")


def test_newest_rate_on_or_before_the_date_wins(app):
    from services.fx_service import get_rate

    with app.app_context():
        app.config["FX_MAX_RATE_AGE_DAYS"] = 30
        _rate(value="0.0100", days_ago=5)
        _rate(value="0.0105", days_ago=1)
        assert get_rate("INR", "USD") == Decimal("0.0105")


def test_a_rate_dated_in_the_future_is_not_used(app):
    from services.fx_service import get_rate

    with app.app_context():
        app.config["FX_MAX_RATE_AGE_DAYS"] = 30
        _rate(value="0.0105", days_ago=1)
        _rate(value="9.9999", days_ago=-5)   # dated five days from now
        assert get_rate("INR", "USD") == Decimal("0.0105")


def test_different_sources_coexist(app):
    from models.fx_rate import FxRate

    with app.app_context():
        _rate(value="0.0105", source="provider_a")
        _rate(value="0.0106", source="provider_b")
        assert FxRate.query.count() == 2


# --------------------------------------------------------------------------- #
# arithmetic
# --------------------------------------------------------------------------- #

def test_conversion_uses_decimal_not_float(app):
    from services.fx_service import convert

    with app.app_context():
        app.config["FX_MARKUP_PERCENT"] = "0"
        _rate(value="0.0105016627")

        got = convert(Decimal("1299.00"), "INR", "USD")
        # 1299 * 0.0105016627 = 13.641659... -> 13.64
        assert got == Decimal("13.64")
        assert isinstance(got, Decimal)


def test_markup_is_applied_on_top_of_the_mid_rate(app):
    from services.fx_service import convert

    with app.app_context():
        app.config["FX_MARKUP_PERCENT"] = "10"
        _rate(value="0.01")

        # 1000 * 0.01 = 10.00, +10% = 11.00
        assert convert(Decimal("1000.00"), "INR", "USD") == Decimal("11.00")


def test_markup_can_be_skipped(app):
    from services.fx_service import convert

    with app.app_context():
        app.config["FX_MARKUP_PERCENT"] = "10"
        _rate(value="0.01")
        assert convert(Decimal("1000.00"), "INR", "USD",
                       apply_markup=False) == Decimal("10.00")


@pytest.mark.parametrize("raw,expected", [
    ("15.21", "15.99"),
    ("15.99", "15.99"),
    ("0.40", "0.99"),
    ("100.00", "100.99"),
    ("99.01", "99.99"),
])
def test_marketing_rounding_never_prices_below_the_input(app, raw, expected):
    """Charm pricing rounds UP. Rounding down would sell under the INR list price."""
    from services.fx_service import apply_marketing_rounding

    with app.app_context():
        app.config["FX_ROUNDING_STYLE"] = "charm_99"
        got = apply_marketing_rounding(Decimal(raw), "USD")
        assert got == Decimal(expected)
        assert got >= Decimal(raw)


def test_marketing_rounding_can_be_turned_off(app):
    from services.fx_service import apply_marketing_rounding

    with app.app_context():
        app.config["FX_ROUNDING_STYLE"] = "none"
        assert apply_marketing_rounding(Decimal("15.21"), "USD") == Decimal("15.21")


def test_to_presentment_returns_the_rate_row_it_used(app):
    """The row is the audit trail — an order stores its id to satisfy I4."""
    from services.fx_service import to_presentment

    with app.app_context():
        app.config["FX_MARKUP_PERCENT"] = "0"
        app.config["FX_ROUNDING_STYLE"] = "none"
        row = _rate(value="0.0105")

        amount, used = to_presentment(Decimal("1000.00"), "USD")
        assert used is not None
        assert used.fx_rate_id == row.fx_rate_id
        assert amount == Decimal("10.50")


def test_to_presentment_in_base_currency_is_a_passthrough(app):
    from services.fx_service import to_presentment

    with app.app_context():
        amount, used = to_presentment(Decimal("1299.00"), "INR")
        assert amount == Decimal("1299.00")
        assert used is None


# --------------------------------------------------------------------------- #
# the snapshot job
# --------------------------------------------------------------------------- #

def test_snapshot_is_skipped_without_an_api_key(app):
    """No key must mean no write and no crash — not a fabricated rate."""
    from models.fx_rate import FxRate
    from services.fx_service import snapshot_rates_from_provider

    with app.app_context():
        app.config["FREECURRENCY_API_KEY"] = None
        assert snapshot_rates_from_provider() == 0
        assert FxRate.query.count() == 0


def test_snapshot_disabled_in_testing_config(app):
    """No test may reach the live FX provider."""
    with app.app_context():
        assert app.config.get("FEATURE_FX_SNAPSHOT") is False
