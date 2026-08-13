"""Superadmin product takedown, and the soft-delete enforcement it depends on.

The enforcement tests matter more than the takedown ones. `deleted_at` existed
before this feature but was only checked by 22 of 61 product queries, so a
"deleted" product could still be added to a cart and ordered. Removing a listing
is worthless if the listing is still purchasable.
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


def _mk_user(email, role=None):
    from auth.models.models import User, UserRole
    u = User(email=email, first_name="A", last_name="B",
             role=role or UserRole.USER, is_email_verified=True)
    u.set_password("StrongPass123")
    db.session.add(u); db.session.flush()
    return u


_SEQ = [0]


def _mk_product(sku="W-1", price="1000.00", stock=10):
    from auth.models.models import MerchantProfile, UserRole
    from models.brand import Brand
    from models.category import Category
    from models.product import Product
    from models.product_stock import ProductStock

    _SEQ[0] += 1
    seq = _SEQ[0]
    owner = _mk_user(f"owner-{seq}@ex.com", UserRole.MERCHANT)
    m = MerchantProfile(user_id=owner.id, business_name="Acme",
                        business_email=f"b{owner.id}@ex.com",
                        business_phone="+919876543210", business_address="1 Rd",
                        country_code="IN", state_province="MH", city="Pune",
                        postal_code="411001", gstin="27ABCDE1234F1Z5")
    db.session.add(m); db.session.flush()
    c = Category(name=f"Cat{seq}", slug=f"cat{seq}"); db.session.add(c)
    b = Brand(name=f"Br{seq}", slug=f"br{seq}"); db.session.add(b)
    db.session.flush()

    p = Product(merchant_id=m.id, category_id=c.category_id, brand_id=b.brand_id,
                sku=sku, product_name=f"Widget {sku}", product_description="A widget",
                cost_price=Decimal("500.00"), selling_price=Decimal(price),
                active_flag=True, approval_status="approved")
    db.session.add(p); db.session.flush()
    db.session.add(ProductStock(product_id=p.product_id, stock_qty=stock))
    db.session.commit()
    return p


def _mk_gst_rule(category_id, rate="18.00"):
    from models.gst_rule import GSTRule
    r = GSTRule(name="GST", category_id=category_id,
                gst_rate_percentage=Decimal(rate), is_active=True,
                start_date=date.today() - timedelta(days=30))
    db.session.add(r); db.session.commit()
    return r


# --------------------------------------------------------------------------- #
# takedown
# --------------------------------------------------------------------------- #

def test_admin_takedown_records_who_and_why(app):
    from controllers.superadmin.product_deletion_controller import delete_products

    with app.app_context():
        p = _mk_product()
        admin = _mk_user("admin@ex.com")
        db.session.commit()

        result = delete_products([p.product_id], admin.id, "Counterfeit branding")

        assert result["deleted_count"] == 1
        assert p.deleted_at is not None
        assert p.deleted_by_role == "admin"
        assert p.deleted_by_user_id == admin.id
        assert p.deletion_reason == "Counterfeit branding"
        # Cleared too, so even a query that forgot to check deleted_at hides it.
        assert p.active_flag is False


def test_takedown_notifies_the_merchant_with_the_reason(app):
    """The merchant is told, not left to discover a listing had vanished."""
    from controllers.superadmin.product_deletion_controller import delete_products
    from models.enums import NotificationType
    from models.merchant_notification import MerchantNotification

    with app.app_context():
        p = _mk_product()
        admin = _mk_user("admin@ex.com")
        db.session.commit()
        merchant_id, pid = p.merchant_id, p.product_id

        delete_products([pid], admin.id, "Prohibited item")

        note = MerchantNotification.query.filter_by(merchant_id=merchant_id).first()
        assert note is not None
        assert note.notification_type == NotificationType.PRODUCT_DELETED_BY_ADMIN
        assert "Prohibited item" in note.message
        assert note.related_entity_type == "product"
        assert note.related_entity_id == pid


def test_takedown_releases_the_sku_so_a_new_listing_can_reuse_it(app):
    """products.sku is unique — holding it would block the re-listing we ask for."""
    from controllers.superadmin.product_deletion_controller import delete_products

    with app.app_context():
        p = _mk_product(sku="ACME-1")
        admin = _mk_user("admin@ex.com")
        db.session.commit()

        delete_products([p.product_id], admin.id, "Wrong category")
        assert p.sku != "ACME-1"
        assert "ACME-1" in p.sku          # still legible for an audit

        # The freed code can now be used by a fresh product.
        replacement = _mk_product(sku="ACME-1", price="1200.00")
        assert replacement.product_id != p.product_id


def test_a_reason_is_required(app):
    from controllers.superadmin.product_deletion_controller import (
        ProductDeletionError, delete_products,
    )

    with app.app_context():
        p = _mk_product()
        admin = _mk_user("admin@ex.com")
        db.session.commit()

        with pytest.raises(ProductDeletionError, match="reason"):
            delete_products([p.product_id], admin.id, "   ")
        assert p.deleted_at is None


def test_bulk_takedown_reports_partial_outcomes(app):
    """38 removed and 2 skipped, not a blanket success or failure."""
    from controllers.superadmin.product_deletion_controller import delete_products

    with app.app_context():
        a, b = _mk_product(sku="A-1"), _mk_product(sku="B-1")
        admin = _mk_user("admin@ex.com")
        db.session.commit()

        delete_products([a.product_id], admin.id, "First pass")
        result = delete_products(
            [a.product_id, b.product_id, 999999], admin.id, "Second pass"
        )

        assert result["deleted_count"] == 1          # only b
        assert result["skipped_count"] == 2          # a already gone, 999999 missing
        reasons = {s["reason"] for s in result["skipped"]}
        assert reasons == {"already deleted", "not found"}


def test_bulk_takedown_is_capped(app):
    from controllers.superadmin.product_deletion_controller import (
        MAX_BULK_DELETE, ProductDeletionError, delete_products,
    )

    with app.app_context():
        admin = _mk_user("admin@ex.com")
        db.session.commit()
        with pytest.raises(ProductDeletionError, match="at most"):
            delete_products(list(range(MAX_BULK_DELETE + 1)), admin.id, "too many")


def test_takedown_does_not_destroy_order_history(app):
    """Soft delete, because order_items reference products."""
    from controllers.superadmin.product_deletion_controller import delete_products
    from models.product import Product

    with app.app_context():
        p = _mk_product()
        admin = _mk_user("admin@ex.com")
        db.session.commit()
        pid = p.product_id

        delete_products([pid], admin.id, "Policy")
        # The row still exists and is still readable.
        assert Product.query.get(pid) is not None


# --------------------------------------------------------------------------- #
# enforcement — the half that was already broken
# --------------------------------------------------------------------------- #

def test_a_deleted_product_cannot_be_added_to_a_cart(app):
    from controllers.cart_controller import CartController
    from controllers.superadmin.product_deletion_controller import delete_products

    with app.app_context():
        p = _mk_product()
        admin = _mk_user("admin@ex.com")
        buyer = _mk_user("buyer@ex.com")
        db.session.commit()

        delete_products([p.product_id], admin.id, "Policy")

        with pytest.raises(ValueError):
            CartController.add_to_cart(buyer.id, p.product_id, 1)


def test_a_deleted_product_cannot_be_quoted(app):
    """The server-authoritative checkout path must refuse it by name."""
    from controllers.superadmin.product_deletion_controller import delete_products
    from services.checkout_quote_service import QuoteError, build_quote

    with app.app_context():
        p = _mk_product()
        _mk_gst_rule(p.category_id)
        admin = _mk_user("admin@ex.com")
        buyer = _mk_user("buyer@ex.com")
        db.session.commit()
        pid = p.product_id

        # Quotable before the takedown.
        assert build_quote(buyer.id, {"items": [{"product_id": pid, "quantity": 1}]})

        delete_products([pid], admin.id, "Policy")

        with pytest.raises(QuoteError, match="no longer available"):
            build_quote(buyer.id, {"items": [{"product_id": pid, "quantity": 1}]})


def test_a_deleted_product_cannot_be_ordered(app):
    from controllers.order_controller import OrderController
    from controllers.superadmin.product_deletion_controller import delete_products

    with app.app_context():
        p = _mk_product()
        _mk_gst_rule(p.category_id)
        admin = _mk_user("admin@ex.com")
        buyer = _mk_user("buyer@ex.com")
        db.session.commit()
        pid = p.product_id

        delete_products([pid], admin.id, "Policy")

        with pytest.raises(ValueError, match="no longer available"):
            OrderController.create_order(buyer.id, {
                "items": [{"product_id": pid, "quantity": 1}],
                "payment_method": "upi",
            })


def test_serializer_exposes_the_removed_by_admin_flag(app):
    """So the merchant dashboard can explain the removal rather than hide it."""
    from controllers.superadmin.product_deletion_controller import delete_products

    with app.app_context():
        p = _mk_product()
        admin = _mk_user("admin@ex.com")
        db.session.commit()

        assert p.serialize()["removed_by_admin"] is False

        delete_products([p.product_id], admin.id, "Counterfeit")
        out = p.serialize()
        assert out["removed_by_admin"] is True
        assert out["deleted_by_role"] == "admin"
        assert out["deletion_reason"] == "Counterfeit"


def test_a_merchant_delete_is_not_marked_as_admin_removal(app):
    """The two kinds of deletion must stay distinguishable."""
    from models.product import Product

    with app.app_context():
        p = _mk_product()
        db.session.commit()

        # What MerchantProductController.delete does.
        p.deleted_at = db.func.current_timestamp()
        db.session.commit()

        out = Product.query.get(p.product_id).serialize()
        assert out["removed_by_admin"] is False
        assert out["deleted_by_role"] is None


def test_cart_line_reports_a_removed_product_as_unavailable(app):
    """The cart must mark the line, not let the customer find out at checkout.

    Both serializers used to report is_deleted unconditionally False — the model
    hardcoded it, and the route checked `hasattr(product, 'is_deleted')` on a model
    that only has `deleted_at`, so the flag never fired at all.
    """
    from controllers.cart_controller import CartController
    from controllers.superadmin.product_deletion_controller import delete_products
    from models.cart import CartItem

    with app.app_context():
        p = _mk_product()
        admin = _mk_user("admin@ex.com")
        buyer = _mk_user("buyer@ex.com")
        db.session.commit()
        pid = p.product_id

        CartController.add_to_cart(buyer.id, pid, 1)
        line = CartItem.query.filter_by(product_id=pid).first()
        assert line.serialize()["product"]["is_deleted"] is False
        assert line.serialize()["product"]["unavailable_reason"] is None

        delete_products([pid], admin.id, "Counterfeit")
        db.session.expire_all()

        out = CartItem.query.filter_by(product_id=pid).first().serialize()
        assert out["product"]["is_deleted"] is True
        assert "removed by AOIN" in out["product"]["unavailable_reason"]


def test_merchant_removal_gets_a_different_cart_message(app):
    """An admin takedown and a merchant retiring stock read differently."""
    from controllers.cart_controller import CartController
    from models.cart import CartItem

    with app.app_context():
        p = _mk_product()
        buyer = _mk_user("buyer@ex.com")
        db.session.commit()
        pid = p.product_id

        CartController.add_to_cart(buyer.id, pid, 1)
        p.deleted_at = db.func.current_timestamp()      # merchant's own delete
        db.session.commit()
        db.session.expire_all()

        reason = CartItem.query.filter_by(product_id=pid).first().serialize()["product"]["unavailable_reason"]
        assert "no longer sold by the merchant" in reason


def test_takedown_survives_a_failing_notification(app):
    """The exact production failure: an unmigrated MySQL ENUM rejects the new
    notification_type, and the takedown must still stand.

    The first version added notifications to the same session and wrapped the
    add() in try/except. session.add() does not touch the database, so the error
    surfaced at commit() outside the guard and rolled the whole takedown back —
    the admin saw a failure and the product stayed on sale.
    """
    from unittest.mock import patch

    from controllers.superadmin import product_deletion_controller as ctl
    from models.product import Product

    with app.app_context():
        p = _mk_product()
        admin = _mk_user("admin@ex.com")
        db.session.commit()
        pid = p.product_id

        with patch.object(
            ctl, "MerchantNotification",
            side_effect=Exception("Data truncated for column 'notification_type'"),
        ):
            result = ctl.delete_products([pid], admin.id, "Counterfeit")

        assert result["deleted_count"] == 1
        db.session.expire_all()
        fresh = Product.query.get(pid)
        assert fresh.deleted_at is not None, "takedown was rolled back by a notification"
        assert fresh.deleted_by_role == "admin"


def test_notification_enum_covers_every_python_member(app):
    """Guards the schema drift that caused the outage.

    If someone adds a NotificationType member without running the migration that
    widens the MySQL ENUM, inserts fail at runtime. This at least pins the
    migration to the enum so the two are edited together.
    """
    from models.enums import NotificationType
    from run_migrations import migrate_notification_type_enum

    with app.app_context():
        # On SQLite this is a no-op that must still report success.
        assert migrate_notification_type_enum() is True
        assert "PRODUCT_DELETED_BY_ADMIN" in [m.name for m in NotificationType]
