"""Tests for the order invoice (GST PDF) endpoint and data assembly."""
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


def _mk_user(email, role=None):
    from auth.models.models import User, UserRole
    u = User(email=email, first_name="Bob", last_name="Buyer",
             role=role or UserRole.USER, is_email_verified=True)
    u.set_password("StrongPass123")
    db.session.add(u)
    db.session.flush()
    return u


def _mk_merchant(owner, state="Maharashtra", gstin="27ABCDE1234F1Z5"):
    from auth.models.models import MerchantProfile
    m = MerchantProfile(
        user_id=owner.id, business_name="Acme Seller", business_email=f"sell{owner.id}@ex.com",
        business_phone="+919876543210", business_address="1 Market Rd",
        country_code="IN", state_province=state, city="Pune", postal_code="411001",
        gstin=gstin,
    )
    db.session.add(m)
    db.session.flush()
    return m


def _mk_address(user, state="Maharashtra"):
    from models.user_address import UserAddress
    from models.enums import AddressTypeEnum
    a = UserAddress(
        user_id=user.id, contact_name="Bob Buyer", contact_phone="+919811111111",
        address_line1="42 Residency Rd", city="Pune", state_province=state,
        postal_code="411001", country_code="IN", address_type=AddressTypeEnum.SHIPPING,
    )
    db.session.add(a)
    db.session.flush()
    return a


def _mk_paid_order(user, merchant, addr, buyer_state="Maharashtra", paid=True):
    from models.order import Order, OrderItem
    from models.enums import OrderStatusEnum, PaymentStatusEnum, PaymentMethodEnum
    order = Order(
        user_id=user.id,
        order_status=OrderStatusEnum.PROCESSING,
        subtotal_amount=Decimal("100.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("18.00"),
        shipping_amount=Decimal("0.00"),
        total_amount=Decimal("118.00"),
        currency="INR",
        payment_method=PaymentMethodEnum.CREDIT_CARD,
        payment_status=PaymentStatusEnum.SUCCESSFUL if paid else PaymentStatusEnum.PENDING,
        shipping_address_id=addr.address_id,
        billing_address_id=addr.address_id,
    )
    db.session.add(order)
    db.session.flush()
    item = OrderItem(
        order_id=order.order_id, product_id=None, merchant_id=merchant.id,
        product_name_at_purchase="Widget", sku_at_purchase="W-1",
        quantity=1,
        final_base_price_for_gst_calc=Decimal("100.00"),
        gst_rate_applied_at_purchase=Decimal("18.00"),
        gst_amount_per_unit=Decimal("18.00"),
        unit_price_inclusive_gst=Decimal("118.00"),
        line_item_total_inclusive_gst=Decimal("118.00"),
    )
    db.session.add(item)
    db.session.commit()
    return order


def _login(client, user_id):
    from flask_jwt_extended import create_access_token
    from auth.models.models import UserRole
    token = create_access_token(identity=str(user_id), additional_claims={"role": UserRole.USER.value})
    return {"Authorization": f"Bearer {token}"}


def test_invoice_pdf_download_ok(client, app):
    with app.app_context():
        seller_owner = _mk_user("sellerowner@ex.com")
        m = _mk_merchant(seller_owner)
        buyer = _mk_user("buyer@ex.com")
        addr = _mk_address(buyer)
        order = _mk_paid_order(buyer, m, addr)
        oid, bid = order.order_id, buyer.id

    resp = client.get(f"/api/orders/{oid}/invoice", headers=_login(client, bid))
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    assert resp.headers["Content-Type"] == "application/pdf"
    assert resp.headers["Content-Disposition"].startswith("attachment")
    body = resp.get_data()
    assert body[:4] == b"%PDF"  # real PDF
    assert len(body) > 1000


def test_invoice_requires_owner(client, app):
    with app.app_context():
        seller_owner = _mk_user("so2@ex.com")
        m = _mk_merchant(seller_owner)
        buyer = _mk_user("buyer2@ex.com")
        other = _mk_user("other@ex.com")
        addr = _mk_address(buyer)
        order = _mk_paid_order(buyer, m, addr)
        oid, other_id = order.order_id, other.id

    resp = client.get(f"/api/orders/{oid}/invoice", headers=_login(client, other_id))
    assert resp.status_code == 403


def test_invoice_unpaid_order_blocked(client, app):
    with app.app_context():
        seller_owner = _mk_user("so3@ex.com")
        m = _mk_merchant(seller_owner)
        buyer = _mk_user("buyer3@ex.com")
        addr = _mk_address(buyer)
        order = _mk_paid_order(buyer, m, addr, paid=False)
        oid, bid = order.order_id, buyer.id

    resp = client.get(f"/api/orders/{oid}/invoice", headers=_login(client, bid))
    assert resp.status_code == 400


def test_invoice_missing_order_404(client, app):
    with app.app_context():
        buyer = _mk_user("buyer4@ex.com")
        bid = buyer.id
    resp = client.get("/api/orders/NOPE-123/invoice", headers=_login(client, bid))
    assert resp.status_code == 404


def test_invoice_requires_auth(client):
    resp = client.get("/api/orders/whatever/invoice")
    assert resp.status_code in (401, 422)  # missing JWT


def test_gst_split_intra_state(app):
    # Same seller/buyer state -> CGST + SGST, each half of 18.00 = 9.00.
    with app.app_context():
        from services.invoice_service import build_invoice_data
        seller_owner = _mk_user("so5@ex.com")
        m = _mk_merchant(seller_owner, state="Maharashtra")
        buyer = _mk_user("buyer5@ex.com")
        addr = _mk_address(buyer, state="Maharashtra")
        order = _mk_paid_order(buyer, m, addr)
        data = build_invoice_data(order.order_id, buyer.id)
        assert data["tax_mode"] == "CGST_SGST"
        row = data["tax_summary"][0]
        assert row["cgst"] == Decimal("9.00")
        assert row["sgst"] == Decimal("9.00")
        assert data["totals"]["tax_total"] == Decimal("18.00")


def test_gst_split_inter_state(app):
    # Different seller/buyer state -> IGST = full 18.00.
    with app.app_context():
        from services.invoice_service import build_invoice_data
        seller_owner = _mk_user("so6@ex.com")
        m = _mk_merchant(seller_owner, state="Maharashtra")
        buyer = _mk_user("buyer6@ex.com")
        addr = _mk_address(buyer, state="Karnataka")
        order = _mk_paid_order(buyer, m, addr, buyer_state="Karnataka")
        data = build_invoice_data(order.order_id, buyer.id)
        assert data["tax_mode"] == "IGST"
        assert data["tax_summary"][0]["igst"] == Decimal("18.00")


def test_gst_fallback_when_seller_state_unknown(app):
    # Seller has no state -> single combined GST line (no split).
    with app.app_context():
        from services.invoice_service import build_invoice_data
        from auth.models.models import MerchantProfile
        seller_owner = _mk_user("so7@ex.com")
        m = _mk_merchant(seller_owner, state="Maharashtra")
        # Blank the seller state to trigger fallback
        m.state_province = ""
        db.session.commit()
        buyer = _mk_user("buyer7@ex.com")
        addr = _mk_address(buyer, state="Karnataka")
        order = _mk_paid_order(buyer, m, addr)
        data = build_invoice_data(order.order_id, buyer.id)
        assert data["tax_mode"] == "GST"
        assert data["tax_summary"][0]["total_tax"] == Decimal("18.00")
