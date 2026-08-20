"""Phase 7: charging in a presentment currency (USD).

Covers the assertions docs/MULTI_CURRENCY.md names for this work:
  * a missing FX rate NEVER returns 1.0 (an $85 item must not become an Rs 85 sale);
  * with the flag off the quote is INR, untouched;
  * with the flag on + a usable rate the quote gains a USD presentment whose parts
    reconstruct the charged total exactly (I5), while the INR book columns stay INR (I1);
  * with the flag on but no rate, checkout falls back to INR rather than breaking.
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
        # Deterministic FX maths: no markup, no charm rounding, generous staleness.
        application.config["FEATURE_MULTI_CURRENCY"] = True
        application.config["FX_QUOTE_CURRENCIES"] = "USD"
        application.config["FX_MARKUP_PERCENT"] = "0"
        application.config["FX_ROUNDING_STYLE"] = "none"
        application.config["FX_MAX_RATE_AGE_DAYS"] = 3650
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


# --------------------------------------------------------------------------- #
# minimal seeding (mirrors tests/test_checkout_quote.py)
# --------------------------------------------------------------------------- #

def _mk_user(email):
    from auth.models.models import User, UserRole
    u = User(email=email, first_name="Bob", last_name="Buyer",
             role=UserRole.USER, is_email_verified=True)
    u.set_password("StrongPass123")
    db.session.add(u); db.session.flush()
    return u


def _mk_merchant(owner):
    from auth.models.models import MerchantProfile
    m = MerchantProfile(
        user_id=owner.id, business_name="Acme Seller", business_email=f"s{owner.id}@ex.com",
        business_phone="+919876543210", business_address="1 Market Rd",
        country_code="IN", state_province="Maharashtra", city="Pune",
        postal_code="411001", gstin="27ABCDE1234F1Z5",
    )
    db.session.add(m); db.session.flush()
    return m


def _seed(price="1180.00", stock=10):
    from models.category import Category
    from models.brand import Brand
    from models.product import Product
    from models.product_stock import ProductStock
    from models.gst_rule import GSTRule

    owner = _mk_user("owner@ex.com")
    merchant = _mk_merchant(owner)
    cat = Category(name="Widgets", slug="widgets"); db.session.add(cat); db.session.flush()
    brand = Brand(name="Acme", slug="acme"); db.session.add(brand); db.session.flush()
    p = Product(
        merchant_id=merchant.id, category_id=cat.category_id, brand_id=brand.brand_id,
        sku="W-1", product_name="Widget", product_description="A widget",
        cost_price=Decimal("500.00"), selling_price=Decimal(price),
        active_flag=True, approval_status="approved",
    )
    db.session.add(p); db.session.flush()
    db.session.add(ProductStock(product_id=p.product_id, stock_qty=stock))
    db.session.add(GSTRule(name="GST 18", category_id=cat.category_id,
                           gst_rate_percentage=Decimal("18.00"), is_active=True,
                           start_date=date.today() - timedelta(days=30)))
    buyer = _mk_user("buyer@ex.com")
    db.session.commit()
    return buyer, p


def _seed_rate(rate="0.0120"):
    from services.fx_service import record_rate
    record_rate("INR", "USD", Decimal(rate), date.today(), "test")


# --------------------------------------------------------------------------- #
# the single most valuable test in the doc's list
# --------------------------------------------------------------------------- #

def test_missing_rate_never_returns_one(app):
    """A silent 1.0 fallback is how an $85 item becomes an Rs 85 sale."""
    from services.fx_service import get_rate, NoFxRateError

    with app.app_context():
        # No rate seeded.
        with pytest.raises(NoFxRateError):
            get_rate("INR", "USD")
        # Same-currency is the ONE legitimate 1.0, and only that.
        assert get_rate("USD", "USD") == Decimal("1")


# --------------------------------------------------------------------------- #
# quote presentment
# --------------------------------------------------------------------------- #

def test_flag_off_keeps_quote_in_inr(app):
    from services.checkout_quote_service import build_quote

    with app.app_context():
        app.config["FEATURE_MULTI_CURRENCY"] = False
        _seed_rate()
        buyer, product = _seed()
        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1}],
            "presentment_currency": "USD",
        })
        assert quote.is_presentment is False
        assert quote.charge_currency == "INR"
        assert quote.charge_amount_minor == 118000
        assert quote.presentment_currency is None


def test_usd_presentment_reconciles_and_keeps_inr_book(app):
    from services.checkout_quote_service import build_quote

    with app.app_context():
        _seed_rate("0.0120")          # 1 INR = 0.012 USD
        buyer, product = _seed()      # 1180 INR incl. GST
        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 2}],
            "presentment_currency": "usd",  # case-insensitive
        })

        # Book columns stay INR (I1).
        assert quote.currency == "INR"
        assert quote.total_amount == Decimal("2360.00")
        assert quote.total_amount_minor == 236000

        # Presentment is USD; charge_* follows it.
        assert quote.presentment_currency == "USD"
        assert quote.charge_currency == "USD"
        # 2360 * 0.012 = 28.32
        assert quote.presentment_total_amount == Decimal("28.32")
        assert quote.charge_amount_minor == 2832
        assert quote.fx_rate_id is not None

        # I5: parts reconstruct the charged total exactly.
        p = quote
        assert (p.presentment_subtotal_amount + p.presentment_tax_amount
                - p.presentment_discount_amount + p.presentment_shipping_amount
                == p.presentment_total_amount)


def test_no_rate_falls_back_to_inr_without_crashing(app):
    from services.checkout_quote_service import build_quote

    with app.app_context():
        # Flag on, USD requested, but NO rate seeded.
        buyer, product = _seed()
        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1}],
            "presentment_currency": "USD",
        })
        assert quote.is_presentment is False
        assert quote.charge_currency == "INR"
        assert quote.charge_amount_minor == 118000


def test_unsupported_currency_is_ignored(app):
    from services.checkout_quote_service import build_quote

    with app.app_context():
        _seed_rate()
        buyer, product = _seed()
        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1}],
            "presentment_currency": "EUR",  # not in FX_QUOTE_CURRENCIES
        })
        assert quote.is_presentment is False
        assert quote.charge_currency == "INR"
