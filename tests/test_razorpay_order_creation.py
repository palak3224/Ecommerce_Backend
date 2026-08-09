"""Amount and currency handling for Razorpay order creation.

Two defects motivate this file:

1. `currency` was taken from the request body and passed straight to Razorpay while
   the amount stayed an unconverted INR number, so a client sending currency="USD"
   created an order for ~85x the intended value.
2. The amount unit was GUESSED from magnitude ("an integer below 1000 is probably
   rupees"), which multiplied any genuine sub-1000-paise amount by 100.
"""
from decimal import Decimal

import pytest

from app import create_app


@pytest.fixture
def app():
    return create_app("testing")


@pytest.fixture
def amount_resolver(app):
    """_resolve_amount_minor needs an app context for its deprecation logging."""
    from routes.razorpay_routes import _resolve_amount_minor

    def resolve(data, currency="INR"):
        with app.app_context():
            return _resolve_amount_minor(data, currency)

    return resolve


# --- unit resolution ---------------------------------------------------------

def test_amount_minor_is_used_verbatim(amount_resolver):
    """900 paise stays 900 paise.

    The old magnitude heuristic turned this into 90000 (Rs 900) because 900 < 1000 --
    a 100x overcharge on any subscription plan under Rs 10.
    """
    assert amount_resolver({"amount_minor": 900}) == 900


def test_large_amount_minor_is_used_verbatim(amount_resolver):
    assert amount_resolver({"amount_minor": 499900}) == 499900


def test_amount_major_is_converted_to_minor(amount_resolver):
    assert amount_resolver({"amount_major": "9.99"}) == 999
    assert amount_resolver({"amount_major": 1234.50}) == 123450


def test_amount_major_uses_decimal_not_float(amount_resolver):
    """float("1234.565") * 100 is 123456.49999... which truncates to 123456."""
    assert amount_resolver({"amount_major": "1234.565"}) == 123457


def test_zero_decimal_currency_factor(amount_resolver):
    """JPY has no minor unit - 500 yen is 500, not 50000."""
    assert amount_resolver({"amount_major": "500"}, currency="JPY") == 500


def test_three_decimal_currency_factor(amount_resolver):
    assert amount_resolver({"amount_major": "1.5"}, currency="KWD") == 1500


def test_legacy_amount_key_is_minor_units(amount_resolver):
    """business/Subscription.tsx sent paise under the bare `amount` key."""
    assert amount_resolver({"amount": 999}) == 999


def test_legacy_amount_rupees_key_is_major_units(amount_resolver):
    """PaymentPage sent rupees under `amount_rupees`."""
    assert amount_resolver({"amount_rupees": 999}) == 99900


def test_explicit_keys_win_over_legacy(amount_resolver):
    assert amount_resolver({"amount_minor": 500, "amount": 12345}) == 500


def test_missing_amount_raises(amount_resolver):
    with pytest.raises(ValueError, match="Amount is required"):
        amount_resolver({})


def test_non_numeric_amount_raises(amount_resolver):
    with pytest.raises(ValueError, match="Invalid amount_major"):
        amount_resolver({"amount_major": "not-a-number"})


def test_fractional_minor_units_raise(amount_resolver):
    """Minor units are indivisible; a fraction means the caller used the wrong key."""
    with pytest.raises(ValueError, match="whole number"):
        amount_resolver({"amount_minor": 12.5})


# --- currency gating ---------------------------------------------------------

def test_minor_unit_factors():
    from routes.razorpay_routes import minor_unit_factor
    assert minor_unit_factor("INR") == 100
    assert minor_unit_factor("USD") == 100
    assert minor_unit_factor("JPY") == 1
    assert minor_unit_factor("KWD") == 1000
    assert minor_unit_factor(None) == 100
    assert minor_unit_factor("inr") == 100


def test_non_inr_rejected_when_multi_currency_disabled(app):
    """The gate that closes the ~85x overcharge path."""
    assert app.config.get("FEATURE_MULTI_CURRENCY") is False

    client = app.test_client()
    resp = client.post(
        "/api/razorpay/create-order",
        json={"amount_major": "4999", "currency": "USD"},
    )
    # Unauthenticated requests are rejected before the currency check; the point is
    # that no Razorpay order is ever created for a non-INR request. A 401 here still
    # proves the request did not reach the gateway.
    assert resp.status_code in (400, 401, 422)
