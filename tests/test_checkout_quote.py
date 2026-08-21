"""Phase 4: server-authoritative checkout quotes.

The assertions here are the ones docs/MULTI_CURRENCY.md section 8 names for this
phase: the quote total equals the order total exactly, a client-stated amount is
ignored, quotes expire, quotes are single-use, verify rejects an amount or currency
mismatch, gateway references are actually committed, and rounding closes over
fuzzed baskets.
"""
from datetime import date, datetime, timedelta
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


@pytest.fixture
def client(app):
    return app.test_client()


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

def _mk_user(email):
    from auth.models.models import User, UserRole
    u = User(email=email, first_name="Bob", last_name="Buyer",
             role=UserRole.USER, is_email_verified=True)
    u.set_password("StrongPass123")
    db.session.add(u)
    db.session.flush()
    return u


def _mk_merchant(owner):
    from auth.models.models import MerchantProfile
    m = MerchantProfile(
        user_id=owner.id, business_name="Acme Seller", business_email=f"s{owner.id}@ex.com",
        business_phone="+919876543210", business_address="1 Market Rd",
        country_code="IN", state_province="Maharashtra", city="Pune",
        postal_code="411001", gstin="27ABCDE1234F1Z5",
    )
    db.session.add(m)
    db.session.flush()
    return m


def _mk_category(name="Widgets"):
    from models.category import Category
    c = Category(name=name, slug=name.lower())
    db.session.add(c)
    db.session.flush()
    return c


def _mk_brand(name="Acme"):
    from models.brand import Brand
    b = Brand(name=name, slug=name.lower())
    db.session.add(b)
    db.session.flush()
    return b


def _mk_product(merchant, category, brand, price="1180.00", sku="W-1", stock=10,
                special=None):
    from models.product import Product
    from models.product_stock import ProductStock
    p = Product(
        merchant_id=merchant.id, category_id=category.category_id, brand_id=brand.brand_id,
        sku=sku, product_name=f"Widget {sku}", product_description="A widget",
        cost_price=Decimal("500.00"), selling_price=Decimal(price),
        special_price=Decimal(special) if special else None,
        special_start=date.today() - timedelta(days=1) if special else None,
        special_end=date.today() + timedelta(days=1) if special else None,
        active_flag=True, approval_status="approved",
    )
    db.session.add(p)
    db.session.flush()
    db.session.add(ProductStock(product_id=p.product_id, stock_qty=stock))
    db.session.flush()
    return p


def _mk_gst_rule(category, rate="18.00"):
    from models.gst_rule import GSTRule
    r = GSTRule(
        name=f"GST {rate}", category_id=category.category_id,
        gst_rate_percentage=Decimal(rate), is_active=True,
        start_date=date.today() - timedelta(days=30),
    )
    db.session.add(r)
    db.session.flush()
    return r


def _login(client, user_id):
    from flask_jwt_extended import create_access_token
    from auth.models.models import UserRole
    token = create_access_token(identity=str(user_id),
                                additional_claims={"role": UserRole.USER.value})
    return {"Authorization": f"Bearer {token}"}


def _seed(price="1180.00", stock=10, special=None):
    """A buyer, a priced product with stock, and a GST rule. Returns (user, product)."""
    owner = _mk_user("owner@ex.com")
    merchant = _mk_merchant(owner)
    cat = _mk_category()
    brand = _mk_brand()
    product = _mk_product(merchant, cat, brand, price=price, stock=stock, special=special)
    _mk_gst_rule(cat)
    buyer = _mk_user("buyer@ex.com")
    db.session.commit()
    return buyer, product


# --------------------------------------------------------------------------- #
# pricing
# --------------------------------------------------------------------------- #

def test_quote_prices_basket_from_the_database(app):
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="1180.00")
        quote = build_quote(buyer.id, {"items": [{"product_id": product.product_id,
                                                  "quantity": 2}]})

        assert quote.total_amount == Decimal("2360.00")
        assert quote.total_amount_minor == 236000
        assert quote.currency == "INR"
        # 1180 inclusive at 18% -> 1000.00 base + 180.00 GST, doubled.
        assert quote.subtotal_amount == Decimal("2000.00")
        assert quote.tax_amount == Decimal("360.00")


def test_client_stated_amount_is_ignored(app):
    """The whole point of the phase: the browser cannot name a price."""
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="1180.00")
        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1}],
            # All of this is a lie the server must not believe.
            "total_amount": "1.00",
            "amount_minor": 100,
            "shipping_amount": "-500.00",
            "item_discount_inclusive": "1179.00",
        })
        assert quote.total_amount == Decimal("1180.00")
        assert quote.total_amount_minor == 118000
        assert quote.discount_amount == Decimal("0.00")
        assert quote.shipping_amount == Decimal("0.00")


def test_unknown_promo_code_grants_no_discount(app):
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="1180.00")
        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1}],
            "promo_code": "NOT-A-REAL-CODE",
        })
        assert quote.discount_amount == Decimal("0.00")
        assert quote.total_amount == Decimal("1180.00")


def test_expired_promotion_is_not_honoured(app):
    from models.enums import DiscountType
    from models.promotion import Promotion
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="1180.00")
        db.session.add(Promotion(
            code="EXPIRED10", discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("10.00"), active_flag=True,
            start_date=date.today() - timedelta(days=30),
            end_date=date.today() - timedelta(days=1),
        ))
        db.session.commit()

        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1}],
            "promo_code": "EXPIRED10",
        })
        assert quote.discount_amount == Decimal("0.00")
        assert quote.total_amount == Decimal("1180.00")


def test_active_promotion_is_applied_server_side(app):
    from models.enums import DiscountType
    from models.promotion import Promotion
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="1000.00")
        db.session.add(Promotion(
            code="SAVE10", discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("10.00"), active_flag=True,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=1),
        ))
        db.session.commit()

        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1}],
            "promo_code": "SAVE10",
        })
        assert quote.discount_amount == Decimal("100.00")
        assert quote.total_amount == Decimal("900.00")


def _mk_promo(code, dtype, value, product_id=None, category_id=None, brand_id=None,
              min_order_value=None, max_discount_amount=None, restricted_to_email=None):
    from models.promotion import Promotion
    p = Promotion(
        code=code, discount_type=dtype, discount_value=Decimal(value),
        active_flag=True, product_id=product_id, category_id=category_id,
        brand_id=brand_id,
        start_date=date.today() - timedelta(days=1),
        end_date=date.today() + timedelta(days=1),
        min_order_value=Decimal(min_order_value) if min_order_value is not None else None,
        max_discount_amount=(
            Decimal(max_discount_amount) if max_discount_amount is not None else None
        ),
        restricted_to_email=restricted_to_email,
    )
    db.session.add(p)
    db.session.commit()
    return p


def test_sitewide_fixed_promo_applies_once_across_the_basket(app):
    """Not once per unit. A per-unit reading of a fixed promo hands out
    quantity x the intended discount — this is the shape that quietly loses money."""
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="500.00", stock=50)
        _mk_promo("FLAT100", DiscountType.FIXED, "100.00")

        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 4}],
            "promo_code": "FLAT100",
        })

        # 4 x 500 = 2000 basket, 100 off once => 1900, NOT 4 x 100 off => 1600.
        assert quote.discount_amount == Decimal("100.00")
        assert quote.total_amount == Decimal("1900.00")


def test_sitewide_fixed_promo_spreads_across_lines_pro_rata(app):
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        owner = _mk_user("owner@ex.com")
        merchant = _mk_merchant(owner)
        cat = _mk_category()
        brand = _mk_brand()
        cheap = _mk_product(merchant, cat, brand, price="100.00", sku="W-C", stock=50)
        dear = _mk_product(merchant, cat, brand, price="300.00", sku="W-D", stock=50)
        _mk_gst_rule(cat)
        buyer = _mk_user("buyer@ex.com")
        db.session.commit()
        _mk_promo("FLAT80", DiscountType.FIXED, "80.00")

        quote = build_quote(buyer.id, {
            "items": [{"product_id": cheap.product_id, "quantity": 1},
                      {"product_id": dear.product_id, "quantity": 1}],
            "promo_code": "FLAT80",
        })

        # 100 + 300 = 400 basket. 80 off, split 1:3 => 20 and 60.
        assert quote.discount_amount == Decimal("80.00")
        assert quote.total_amount == Decimal("320.00")


def test_sitewide_fixed_promo_is_capped_at_the_basket(app):
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="100.00", stock=50)
        _mk_promo("FLAT9999", DiscountType.FIXED, "9999.00")

        with pytest.raises(Exception):
            # Discount capped at the basket, so the total is zero and refused
            # rather than becoming a negative charge.
            build_quote(buyer.id, {
                "items": [{"product_id": product.product_id, "quantity": 1}],
                "promo_code": "FLAT9999",
            })


def test_targeted_fixed_promo_applies_per_line_capped(app):
    """Targeted fixed is min(line_total, value) per matching line."""
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="500.00", stock=50)
        _mk_promo("ITEM50", DiscountType.FIXED, "50.00", product_id=product.product_id)

        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 3}],
            "promo_code": "ITEM50",
        })

        # One line of 1500, capped fixed 50 on that line — not 50 per unit
        # (which would be 150). The 2 paise shortfall is 50.00/3 rounded DOWN per
        # unit: the discount may never round up past the promotion's own value.
        assert quote.discount_amount == Decimal("49.98")
        assert quote.total_amount == Decimal("1450.02")


def test_targeted_promo_skips_non_matching_products(app):
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        owner = _mk_user("owner@ex.com")
        merchant = _mk_merchant(owner)
        cat = _mk_category()
        brand = _mk_brand()
        hit = _mk_product(merchant, cat, brand, price="200.00", sku="W-H", stock=50)
        miss = _mk_product(merchant, cat, brand, price="200.00", sku="W-M", stock=50)
        _mk_gst_rule(cat)
        buyer = _mk_user("buyer@ex.com")
        db.session.commit()
        _mk_promo("ONLYHIT", DiscountType.PERCENTAGE, "50.00", product_id=hit.product_id)

        quote = build_quote(buyer.id, {
            "items": [{"product_id": hit.product_id, "quantity": 1},
                      {"product_id": miss.product_id, "quantity": 1}],
            "promo_code": "ONLYHIT",
        })

        assert quote.discount_amount == Decimal("100.00")   # 50% of the hit only
        assert quote.total_amount == Decimal("300.00")


def test_promo_code_lookup_is_case_insensitive(app):
    """Matches POST /api/promo-code/apply, which uppercases before looking up."""
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="1000.00")
        _mk_promo("SAVE10", DiscountType.PERCENTAGE, "10.00")

        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1}],
            "promo_code": "  save10  ",
        })
        assert quote.discount_amount == Decimal("100.00")


def test_percentage_over_100_is_clamped(app):
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="500.00", stock=50)
        _mk_promo("BOGUS", DiscountType.PERCENTAGE, "150.00")

        with pytest.raises(Exception):
            # Clamped to 100%, so the basket is zero and refused — never negative.
            build_quote(buyer.id, {
                "items": [{"product_id": product.product_id, "quantity": 1}],
                "promo_code": "BOGUS",
            })


def test_fixed_discount_cannot_drive_a_line_negative(app):
    from models.enums import DiscountType
    from models.promotion import Promotion
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="100.00")
        db.session.add(Promotion(
            code="HUGE", discount_type=DiscountType.FIXED,
            discount_value=Decimal("99999.00"), active_flag=True,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=1),
        ))
        db.session.commit()

        with pytest.raises(Exception):
            # Capped to the item price, so the basket totals zero and is refused
            # rather than becoming a negative charge.
            build_quote(buyer.id, {
                "items": [{"product_id": product.product_id, "quantity": 1}],
                "promo_code": "HUGE",
            })


def test_insufficient_stock_is_refused(app):
    from services.checkout_quote_service import QuoteError, build_quote

    with app.app_context():
        buyer, product = _seed(stock=1)
        with pytest.raises(QuoteError):
            build_quote(buyer.id, {"items": [{"product_id": product.product_id,
                                              "quantity": 5}]})


@pytest.mark.parametrize("price,qty", [
    ("0.01", 3), ("33.33", 3), ("999.99", 7), ("1.05", 11),
    ("12345.67", 2), ("0.03", 97), ("7.77", 13),
])
def test_rounding_closes_over_fuzzed_baskets(app, price, qty):
    """Sigma(lines) + shipping must reconstruct the total exactly — invariant I5."""
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price=price, stock=1000)
        quote = build_quote(buyer.id, {"items": [{"product_id": product.product_id,
                                                  "quantity": qty}]})

        lines_total = sum(i.line_item_total_inclusive_gst for i in quote.items)
        assert quote.total_amount == lines_total + quote.shipping_amount
        # And the integer handed to the gateway is exactly the total, not a re-round.
        assert quote.total_amount_minor == int(
            (quote.total_amount * 100).to_integral_value()
        )


# --------------------------------------------------------------------------- #
# lifecycle: expiry and single use
# --------------------------------------------------------------------------- #

def test_quote_expires(app):
    from models.checkout_quote import CheckoutQuote
    from services.checkout_quote_service import QuoteError, build_quote, load_spendable_quote

    with app.app_context():
        buyer, product = _seed()
        quote = build_quote(buyer.id, {"items": [{"product_id": product.product_id,
                                                  "quantity": 1}]})
        qid, uid = quote.quote_id, buyer.id

        # Still good now.
        assert load_spendable_quote(qid, uid) is not None

        db.session.query(CheckoutQuote).filter_by(quote_id=qid).update(
            {CheckoutQuote.expires_at: datetime.utcnow() - timedelta(seconds=1)}
        )
        db.session.commit()

        with pytest.raises(QuoteError, match="expired"):
            load_spendable_quote(qid, uid)


def test_quote_is_single_use(app):
    """Two consumes of one quote: exactly one wins. Invariant I10."""
    from services.checkout_quote_service import build_quote, consume_quote

    with app.app_context():
        buyer, product = _seed()
        quote = build_quote(buyer.id, {"items": [{"product_id": product.product_id,
                                                  "quantity": 1}]})
        qid = quote.quote_id

        assert consume_quote(qid, order_id="ORD-1") is True
        assert consume_quote(qid, order_id="ORD-2") is False


def test_consumed_quote_cannot_be_loaded_again(app):
    from services.checkout_quote_service import (
        QuoteError, build_quote, consume_quote, load_spendable_quote,
    )

    with app.app_context():
        buyer, product = _seed()
        quote = build_quote(buyer.id, {"items": [{"product_id": product.product_id,
                                                  "quantity": 1}]})
        qid, uid = quote.quote_id, buyer.id
        consume_quote(qid, order_id="ORD-1")
        db.session.commit()

        with pytest.raises(QuoteError, match="already been paid"):
            load_spendable_quote(qid, uid)


def test_another_users_quote_is_not_loadable(app):
    from services.checkout_quote_service import QuoteError, build_quote, load_spendable_quote

    with app.app_context():
        buyer, product = _seed()
        intruder = _mk_user("intruder@ex.com")
        db.session.commit()

        quote = build_quote(buyer.id, {"items": [{"product_id": product.product_id,
                                                  "quantity": 1}]})
        with pytest.raises(QuoteError, match="not found"):
            load_spendable_quote(quote.quote_id, intruder.id)


# --------------------------------------------------------------------------- #
# quote -> order materialisation
# --------------------------------------------------------------------------- #

def test_order_total_equals_quote_total_exactly(app):
    from controllers.order_controller import OrderController
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="999.99", stock=50)
        quote = build_quote(buyer.id, {"items": [{"product_id": product.product_id,
                                                  "quantity": 3}]})

        order = OrderController.create_order_from_quote(
            user_id=buyer.id, quote=quote,
            gateway_refs={"razorpay_order_id": "order_XYZ",
                          "razorpay_payment_id": "pay_XYZ"},
        )

        assert order.total_amount == quote.total_amount
        assert order.subtotal_amount == quote.subtotal_amount
        assert order.tax_amount == quote.tax_amount
        assert order.currency == quote.currency == "INR"


def test_gateway_refs_are_committed(app):
    """Re-query from a fresh session — a dirty in-session object proves nothing."""
    from controllers.order_controller import OrderController
    from models.order import Order
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed()
        quote = build_quote(buyer.id, {"items": [{"product_id": product.product_id,
                                                  "quantity": 1}]})
        order = OrderController.create_order_from_quote(
            user_id=buyer.id, quote=quote,
            gateway_refs={"razorpay_order_id": "order_ABC",
                          "razorpay_payment_id": "pay_ABC"},
        )
        oid = order.order_id

        db.session.expunge_all()
        db.session.remove()

        fresh = Order.query.get(oid)
        assert fresh.razorpay_order_id == "order_ABC"
        assert fresh.razorpay_payment_id == "pay_ABC"
        assert fresh.payment_gateway_transaction_id == "pay_ABC"
        assert fresh.payment_gateway_name == "Razorpay"


def test_materialising_an_order_decrements_stock(app):
    from controllers.order_controller import OrderController
    from models.product_stock import ProductStock
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(stock=10)
        pid = product.product_id
        quote = build_quote(buyer.id, {"items": [{"product_id": pid, "quantity": 4}]})
        OrderController.create_order_from_quote(
            user_id=buyer.id, quote=quote,
            gateway_refs={"razorpay_payment_id": "pay_1"},
        )
        assert ProductStock.query.filter_by(product_id=pid).first().stock_qty == 6


# --------------------------------------------------------------------------- #
# the client-asserted payment hole
# --------------------------------------------------------------------------- #

def test_client_supplied_payment_id_does_not_mark_an_order_paid(app):
    """Posting any string as razorpay_payment_id used to produce a PAID order."""
    from controllers.order_controller import OrderController
    from models.enums import PaymentStatusEnum

    with app.app_context():
        buyer, product = _seed()
        # upi, not a card: the card branch runs its own payment *simulation*, which
        # is a separate pre-existing hole and not what this test is about.
        result = OrderController.create_order(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1}],
            "payment_method": "upi",
            "razorpay_payment_id": "pay_TOTALLY_MADE_UP",
        })

        from models.order import Order
        order = Order.query.get(result["order_id"])
        assert order.payment_status == PaymentStatusEnum.PENDING
        # The reference is still recorded; it just carries no authority.
        assert order.razorpay_payment_id == "pay_TOTALLY_MADE_UP"


# --------------------------------------------------------------------------- #
# HTTP surface
# --------------------------------------------------------------------------- #

def test_quote_endpoint_requires_auth(client, app):
    assert client.post("/api/checkout/quote", json={}).status_code == 401


def test_quote_endpoint_returns_strings_not_floats(client, app):
    """Invariant I9: money leaves the API as strings."""
    with app.app_context():
        buyer, product = _seed()
        headers = _login(client, buyer.id)
        pid = product.product_id

    resp = client.post("/api/checkout/quote",
                       json={"items": [{"product_id": pid, "quantity": 1}]},
                       headers=headers)
    assert resp.status_code == 201
    body = resp.get_json()["data"]
    assert isinstance(body["total_amount"], str)
    assert body["total_amount"] == "1180.00"
    assert isinstance(body["total_amount_minor"], int)


def test_empty_basket_is_refused(client, app):
    with app.app_context():
        buyer = _mk_user("lonely@ex.com")
        db.session.commit()
        headers = _login(client, buyer.id)

    resp = client.post("/api/checkout/quote", json={"items": []}, headers=headers)
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# promotion redemption rules
#
# These guard the rules added for the storefront lead-capture game, but they are
# not game-specific: any promotion can now carry a minimum, a cap, an owner, and
# be spent exactly once.
# --------------------------------------------------------------------------- #

def test_min_order_value_below_threshold_is_refused_loudly(app):
    """Not silently dropped. A customer who deliberately typed a code and sees no
    discount and no reason concludes the site is broken."""
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote, QuoteError

    with app.app_context():
        buyer, product = _seed(price="100.00", stock=50)
        _mk_promo("MIN500", DiscountType.PERCENTAGE, "10.00", min_order_value="500.00")

        with pytest.raises(QuoteError) as exc:
            build_quote(buyer.id, {
                "items": [{"product_id": product.product_id, "quantity": 2}],
                "promo_code": "MIN500",
            })
        assert "minimum order" in str(exc.value).lower()


def test_min_order_value_met_applies_normally(app):
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="100.00", stock=50)
        _mk_promo("MIN500", DiscountType.PERCENTAGE, "10.00", min_order_value="500.00")

        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 6}],
            "promo_code": "MIN500",
        })
        # 600 basket, 10% off.
        assert quote.discount_amount == Decimal("60.00")


def test_max_discount_amount_caps_a_percentage_promo(app):
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="100.00", stock=100)
        _mk_promo("HALFCAP", DiscountType.PERCENTAGE, "50.00", max_discount_amount="120.00")

        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 10}],
            "promo_code": "HALFCAP",
        })
        # 1000 basket, 50% would be 500, capped at 120.
        assert quote.discount_amount == Decimal("120.00")
        assert quote.total_amount == Decimal("880.00")


def test_cap_spreads_across_lines_and_never_exceeds_itself(app):
    """The spread has to sum to exactly the cap. Rounding each line's share
    independently can overshoot by paise per line, which is the difference between
    honouring a ceiling and quietly breaching it."""
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        owner = _mk_user("owner@ex.com")
        merchant = _mk_merchant(owner)
        cat = _mk_category()
        brand = _mk_brand()
        a = _mk_product(merchant, cat, brand, price="100.00", sku="C-A", stock=50)
        b = _mk_product(merchant, cat, brand, price="200.00", sku="C-B", stock=50)
        _mk_gst_rule(cat)
        buyer = _mk_user("buyer@ex.com")
        db.session.commit()
        _mk_promo("CAP77", DiscountType.PERCENTAGE, "50.00", max_discount_amount="77.77")

        quote = build_quote(buyer.id, {
            "items": [{"product_id": a.product_id, "quantity": 1},
                      {"product_id": b.product_id, "quantity": 1}],
            "promo_code": "CAP77",
        })
        assert quote.discount_amount <= Decimal("77.77")
        assert quote.discount_amount == Decimal("77.77")


def test_uncapped_promo_is_unchanged_by_the_cap_code(app):
    """The regression that matters: promotions without a cap must price exactly as
    they did before caps existed."""
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="100.00", stock=100)
        _mk_promo("PLAIN10", DiscountType.PERCENTAGE, "10.00")

        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 10}],
            "promo_code": "PLAIN10",
        })
        assert quote.discount_amount == Decimal("100.00")


def test_a_spent_promotion_cannot_be_spent_again(app):
    from models.enums import DiscountType
    from models.promotion_redemption import PromotionRedemption
    from services.checkout_quote_service import build_quote, QuoteError

    with app.app_context():
        buyer, product = _seed(price="100.00", stock=100)
        promo = _mk_promo("ONCE10", DiscountType.PERCENTAGE, "10.00")

        # First use lands a redemption row, exactly as create_order_from_quote does.
        db.session.add(PromotionRedemption(
            promotion_id=promo.promotion_id, order_id="ORD-1", user_id=buyer.id,
            discount_amount=Decimal("10.00"), redeemed_at=datetime.utcnow(),
        ))
        db.session.commit()

        with pytest.raises(QuoteError) as exc:
            build_quote(buyer.id, {
                "items": [{"product_id": product.product_id, "quantity": 1}],
                "promo_code": "ONCE10",
            })
        assert "already been used" in str(exc.value).lower()


def test_single_use_is_enforced_by_the_database_not_the_check(app):
    """Two concurrent orders both pass validation; the unique index is what stops
    the second one actually spending the code."""
    from models.enums import DiscountType
    from models.promotion_redemption import PromotionRedemption
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        buyer, _ = _seed(price="100.00", stock=100)
        promo = _mk_promo("RACE10", DiscountType.PERCENTAGE, "10.00")

        db.session.add(PromotionRedemption(
            promotion_id=promo.promotion_id, order_id="ORD-A", user_id=buyer.id,
            discount_amount=Decimal("10.00"), redeemed_at=datetime.utcnow(),
        ))
        db.session.commit()

        db.session.add(PromotionRedemption(
            promotion_id=promo.promotion_id, order_id="ORD-B", user_id=buyer.id,
            discount_amount=Decimal("10.00"), redeemed_at=datetime.utcnow(),
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_email_binding_is_recorded_but_not_enforced_by_default(app):
    """Off by default: rejecting a legitimate winner who signed up with a different
    address costs more than a leaked single-use, capped, one-day code."""
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="100.00", stock=100)
        _mk_promo("MINE10", DiscountType.PERCENTAGE, "10.00",
                  restricted_to_email="someone.else@ex.com")

        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1},],
            "promo_code": "MINE10",
        })
        assert quote.discount_amount == Decimal("10.00")


def test_email_binding_is_enforced_when_the_flag_is_on(app):
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote, QuoteError

    with app.app_context():
        buyer, product = _seed(price="100.00", stock=100)
        _mk_promo("MINE10", DiscountType.PERCENTAGE, "10.00",
                  restricted_to_email="someone.else@ex.com")
        app.config["PROMO_EMAIL_BINDING_ENFORCED"] = True
        try:
            with pytest.raises(QuoteError) as exc:
                build_quote(buyer.id, {
                    "items": [{"product_id": product.product_id, "quantity": 1}],
                    "promo_code": "MINE10",
                })
            assert "different account" in str(exc.value).lower()
        finally:
            app.config["PROMO_EMAIL_BINDING_ENFORCED"] = False


def test_business_today_is_one_clock_for_display_and_pricing(app):
    """The bug this prevents: /api/promo-code/apply used the server-local date while
    the quote used UTC. On an IST box between 00:00 and 05:30 those differ, so a
    same-day coupon was advertised as valid and then produced no discount."""
    from services.promotion_service import business_today

    with app.app_context():
        app.config["PROMO_TIMEZONE"] = "Asia/Kolkata"
        # 20:00 UTC on the 1st is already 01:30 IST on the 2nd.
        late_utc = datetime(2026, 3, 1, 20, 0, 0)
        assert business_today(late_utc) == date(2026, 3, 2)
        assert business_today(late_utc) != late_utc.date()


def test_quote_records_which_promotion_it_used(app):
    """Without this the order has no idea what to mark redeemed at capture time."""
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="100.00", stock=100)
        promo = _mk_promo("TRACK10", DiscountType.PERCENTAGE, "10.00")

        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1}],
            "promo_code": "TRACK10",
        })
        assert quote.promotion_id == promo.promotion_id
        assert quote.promo_code == "TRACK10"


def test_paying_a_quote_records_the_redemption_atomically(app):
    """The redemption is written inside create_order_from_quote's transaction, so it
    cannot end up out of step with the order it belongs to."""
    from controllers.order_controller import OrderController
    from models.enums import DiscountType
    from models.order import Order
    from models.promotion_redemption import PromotionRedemption
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed(price="100.00", stock=50)
        promo = _mk_promo("SPEND10", DiscountType.PERCENTAGE, "10.00")
        # Read the ids now: the session is cleared below, which detaches these objects.
        promo_id = promo.promotion_id
        buyer_id = buyer.id

        quote = build_quote(buyer_id, {
            "items": [{"product_id": product.product_id, "quantity": 2}],
            "promo_code": "SPEND10",
        })
        order = OrderController.create_order_from_quote(user_id=buyer_id, quote=quote)
        oid = order.order_id

        db.session.expunge_all()
        db.session.remove()

        redemption = PromotionRedemption.query.filter_by(promotion_id=promo_id).one()
        assert redemption.order_id == oid
        assert redemption.user_id == buyer_id
        assert redemption.discount_amount == Decimal("20.00")

        # And the order itself remembers which promotion it used.
        fresh = Order.query.get(oid)
        assert fresh.promotion_id == promo_id
        assert fresh.promo_code == "SPEND10"


def test_a_code_spent_on_one_order_is_dead_for_the_next_quote(app):
    """End to end: pay with the code, then try to use it again."""
    from controllers.order_controller import OrderController
    from models.enums import DiscountType
    from services.checkout_quote_service import build_quote, QuoteError

    with app.app_context():
        buyer, product = _seed(price="100.00", stock=50)
        _mk_promo("ONEUSE", DiscountType.PERCENTAGE, "10.00")

        first = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1}],
            "promo_code": "ONEUSE",
        })
        OrderController.create_order_from_quote(user_id=buyer.id, quote=first)

        with pytest.raises(QuoteError) as exc:
            build_quote(buyer.id, {
                "items": [{"product_id": product.product_id, "quantity": 1}],
                "promo_code": "ONEUSE",
            })
        assert "already been used" in str(exc.value).lower()


def test_an_order_without_a_promo_writes_no_redemption(app):
    from controllers.order_controller import OrderController
    from models.promotion_redemption import PromotionRedemption
    from services.checkout_quote_service import build_quote

    with app.app_context():
        buyer, product = _seed()
        quote = build_quote(buyer.id, {
            "items": [{"product_id": product.product_id, "quantity": 1}]})
        OrderController.create_order_from_quote(user_id=buyer.id, quote=quote)
        assert PromotionRedemption.query.count() == 0
