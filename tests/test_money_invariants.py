"""Money invariants that must hold before multi-currency work begins.

INR is the base/book currency: merchant prices, GST slabs, platform-fee tiers and
merchant settlement are all denominated in it. These tests lock that in so a stray
"USD" default cannot mislabel an INR amount again.
"""
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


def _mk_user(email="buyer@example.com"):
    from auth.models.models import User, UserRole
    u = User(email=email, first_name="Bob", last_name="Buyer",
             role=UserRole.USER, is_email_verified=True)
    u.set_password("StrongPass123")
    db.session.add(u)
    db.session.flush()
    return u


def test_order_currency_defaults_to_inr(app):
    """An Order created without an explicit currency is INR, not USD."""
    from models.order import Order
    from models.enums import OrderStatusEnum, PaymentStatusEnum

    user = _mk_user()
    order = Order(
        user_id=user.id,
        order_status=OrderStatusEnum.PENDING_PAYMENT,
        subtotal_amount=Decimal("100.00"),
        tax_amount=Decimal("18.00"),
        total_amount=Decimal("118.00"),
        payment_status=PaymentStatusEnum.PENDING,
    )
    db.session.add(order)
    db.session.flush()

    assert order.currency == "INR"


def test_shop_order_currency_defaults_to_inr(app):
    """The shop stack mirrors the marketplace default."""
    from models.shop.shop_order import ShopOrder
    from models.enums import OrderStatusEnum, PaymentStatusEnum

    user = _mk_user("shopbuyer@example.com")
    order = ShopOrder(
        user_id=user.id,
        shop_id=1,
        order_status=OrderStatusEnum.PENDING_PAYMENT,
        subtotal_amount=Decimal("100.00"),
        tax_amount=Decimal("18.00"),
        total_amount=Decimal("118.00"),
        payment_status=PaymentStatusEnum.PENDING,
    )
    db.session.add(order)
    db.session.flush()

    assert order.currency == "INR"


def test_default_currency_config_is_inr(app):
    """config.DEFAULT_CURRENCY exists.

    order_controller previously read a key that was never defined, so its "USD"
    fallback was what actually got written to every order.
    """
    assert app.config.get("DEFAULT_CURRENCY") == "INR"


def test_multi_currency_is_off_by_default(app):
    """Charging in a non-base currency stays gated until the currency layer ships."""
    assert app.config.get("FEATURE_MULTI_CURRENCY") is False


def test_order_serialize_reports_its_currency(app):
    """Whatever is stored is what gets serialized - no hardcoded symbol or code."""
    from models.order import Order
    from models.enums import OrderStatusEnum, PaymentStatusEnum

    user = _mk_user("serialize@example.com")
    order = Order(
        user_id=user.id,
        order_status=OrderStatusEnum.PENDING_PAYMENT,
        subtotal_amount=Decimal("100.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("100.00"),
        payment_status=PaymentStatusEnum.PENDING,
    )
    db.session.add(order)
    db.session.flush()

    assert order.serialize()["currency"] == "INR"
