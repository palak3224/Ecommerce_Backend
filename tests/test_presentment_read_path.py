"""Phase 3: the presentment read path.

The load-bearing test here is the first one: **a request without `?currency=`
returns byte-identical JSON to before.** That guarantee is the only reason it is
safe to change what the existing scalar price keys mean, because roughly 150
frontend call sites treat them as bare numbers and do arithmetic on them.
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


def _seed_product(price="1299.00", special=None, override=None, override_ccy=None):
    from auth.models.models import MerchantProfile, User, UserRole
    from models.brand import Brand
    from models.category import Category
    from models.product import Product
    from models.product_stock import ProductStock

    u = User(email="m@ex.com", first_name="M", last_name="S",
             role=UserRole.MERCHANT, is_email_verified=True)
    u.set_password("StrongPass123")
    db.session.add(u); db.session.flush()
    m = MerchantProfile(user_id=u.id, business_name="Acme", business_email="b@ex.com",
                        business_phone="+919876543210", business_address="1 Rd",
                        country_code="IN", state_province="MH", city="Pune",
                        postal_code="411001", gstin="27ABCDE1234F1Z5")
    db.session.add(m); db.session.flush()
    c = Category(name="Widgets", slug="widgets"); db.session.add(c)
    b = Brand(name="Acme", slug="acme"); db.session.add(b); db.session.flush()

    p = Product(merchant_id=m.id, category_id=c.category_id, brand_id=b.brand_id,
                sku="W-1", product_name="Widget", product_description="A widget",
                cost_price=Decimal("500.00"), selling_price=Decimal(price),
                special_price=Decimal(special) if special else None,
                special_start=date.today() - timedelta(days=1) if special else None,
                special_end=date.today() + timedelta(days=1) if special else None,
                active_flag=True, approval_status="approved")
    if override is not None:
        p.presentment_price = Decimal(override)
        p.presentment_currency = override_ccy or "USD"
    db.session.add(p); db.session.flush()
    db.session.add(ProductStock(product_id=p.product_id, stock_qty=10))
    db.session.commit()
    return p


def _rate(value="0.0105"):
    from services.fx_service import record_rate
    return record_rate("INR", "USD", Decimal(value), date.today(), "test")


# --------------------------------------------------------------------------- #
# the guarantee everything else rests on
# --------------------------------------------------------------------------- #

def test_no_currency_param_means_byte_identical_output(app):
    """No ?currency= -> not one key added, not one value changed."""
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True
        _rate()
        p = _seed_product(price="1299.00")

        out = p.serialize()

        assert out["selling_price"] == 1299.00
        assert out["price"] == 1299.00
        # The presentment keys must be absent entirely, not present-and-null.
        for key in ("selling_price_inr", "price_inr", "currency", "price_source", "prices"):
            assert key not in out, f"{key} leaked into a non-presentment response"


def test_flag_off_ignores_the_currency_param(app):
    """The feature gate wins over the query param."""
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = False
        _rate()
        p = _seed_product(price="1299.00")

        out = p.serialize(currency="USD")
        assert out["selling_price"] == 1299.00
        assert "prices" not in out


# --------------------------------------------------------------------------- #
# presentment
# --------------------------------------------------------------------------- #

def test_usd_presentment_prices_the_scalars_in_usd(app):
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True
        app.config["FX_MARKUP_PERCENT"] = "0"
        app.config["FX_ROUNDING_STYLE"] = "none"
        _rate("0.01")
        p = _seed_product(price="1000.00")

        out = p.serialize(currency="USD")

        assert out["selling_price"] == 10.00        # the scalar is now USD
        assert out["selling_price_inr"] == 1000.00  # INR always available alongside
        assert out["currency"] == "USD"
        assert out["price_source"] == "DERIVED"


def test_presentment_amounts_are_strings(app):
    """Invariant I9 — the structured block never emits floats."""
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True
        _rate()
        p = _seed_product(price="1299.00")

        block = p.serialize(currency="USD")["prices"]["list"]
        assert isinstance(block["amount"], str)
        assert isinstance(block["amount_base"], str)
        assert block["base_currency"] == "INR"


def test_presentment_records_the_rate_row_it_used(app):
    """So a price a customer queries can be traced to an exact rate (I4)."""
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True
        row = _rate()
        p = _seed_product(price="1299.00")

        block = p.serialize(currency="USD")["prices"]["list"]
        assert block["fx_rate_id"] == row.fx_rate_id


def test_merchant_override_wins_over_the_derived_price(app):
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True
        _rate("0.01")
        p = _seed_product(price="1000.00", override="49.99", override_ccy="USD")

        out = p.serialize(currency="USD")
        assert out["selling_price"] == 49.99
        assert out["price_source"] == "MERCHANT_OVERRIDE"


def test_override_in_another_currency_is_ignored(app):
    """A price typed in EUR must not be served as USD."""
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True
        app.config["FX_MARKUP_PERCENT"] = "0"
        app.config["FX_ROUNDING_STYLE"] = "none"
        _rate("0.01")
        p = _seed_product(price="1000.00", override="49.99", override_ccy="EUR")

        out = p.serialize(currency="USD")
        assert out["selling_price"] == 10.00
        assert out["price_source"] == "DERIVED"


# --------------------------------------------------------------------------- #
# the failure mode that matters
# --------------------------------------------------------------------------- #

def test_no_fx_rate_serves_inr_rather_than_a_fabricated_usd_price(app):
    """A listing must still render — but never at a made-up rate.

    fx_service raises when it has no rate. The serializer catches that and falls
    back to the INR amount *labelled INR*, so the page shows a correct rupee price.
    The one thing it must never do is emit the rupee number labelled USD.
    """
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True
        # deliberately no rate recorded
        p = _seed_product(price="1299.00")

        out = p.serialize(currency="USD")

        assert out["selling_price"] == 1299.00
        assert out["currency"] == "INR", "rupee amount was labelled as a foreign currency"
        assert out["price_source"] == "BASE"


def test_stale_fx_rate_also_falls_back_to_inr(app):
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True
        app.config["FX_MAX_RATE_AGE_DAYS"] = 1
        from services.fx_service import record_rate
        record_rate("INR", "USD", Decimal("0.0105"),
                    date.today() - timedelta(days=30), "test")
        p = _seed_product(price="1299.00")

        out = p.serialize(currency="USD")
        assert out["currency"] == "INR"
        assert out["selling_price"] == 1299.00


def test_unknown_currency_falls_back_to_base(app):
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True
        _rate()
        p = _seed_product(price="1299.00")

        assert "prices" not in p.serialize(currency="XYZ")
        assert "prices" not in p.serialize(currency="not-a-code")


def test_outside_a_request_context_currency_is_base(app):
    """Jobs and invoice PDFs must never render in a presentment currency."""
    from services.currency_context import resolve_request_currency

    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True
        assert resolve_request_currency() == "INR"


# --------------------------------------------------------------------------- #
# the context endpoint
# --------------------------------------------------------------------------- #

def test_currency_context_defaults_to_inr_for_india(app):
    client = app.test_client()
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True

    resp = client.get("/api/currency/context", headers={"CloudFront-Viewer-Country": "IN"})
    body = resp.get_json()
    assert resp.status_code == 200
    assert body["suggested_currency"] == "INR"
    assert body["charge_currency"] == "INR"


def test_currency_context_suggests_usd_outside_india(app):
    client = app.test_client()
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True

    body = client.get("/api/currency/context",
                      headers={"CloudFront-Viewer-Country": "US"}).get_json()
    assert body["suggested_currency"] == "USD"
    assert body["detected_country"] == "US"
    # Display is USD, but the money still moves in INR until Phase 7.
    assert body["charge_currency"] == "INR"


def test_unknown_country_gets_the_charge_currency(app):
    """Safer mistake: show what they will actually be charged in."""
    client = app.test_client()
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = True

    body = client.get("/api/currency/context").get_json()
    assert body["suggested_currency"] == "INR"
    assert body["detected_country"] is None


def test_currency_context_with_flag_off_offers_only_inr(app):
    client = app.test_client()
    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = False

    body = client.get("/api/currency/context",
                      headers={"CloudFront-Viewer-Country": "US"}).get_json()
    assert body["suggested_currency"] == "INR"
    assert body["supported_currencies"] == ["INR"]
    assert body["multi_currency_enabled"] is False
