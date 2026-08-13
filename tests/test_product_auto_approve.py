"""New products go live without waiting for an admin.

The gate is a config flag, not deleted code: it is a policy decision that may be
wanted back — at scale, or for a new merchant's first listings — and restoring it
should not need a deploy. Both states are tested, so turning it back on cannot
quietly break.
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


_SEQ = [0]


def _mk_merchant_user():
    from auth.models.models import MerchantProfile, User, UserRole
    _SEQ[0] += 1
    seq = _SEQ[0]
    u = User(email=f"m{seq}@ex.com", first_name="M", last_name="S",
             role=UserRole.MERCHANT, is_email_verified=True)
    u.set_password("StrongPass123")
    db.session.add(u); db.session.flush()
    m = MerchantProfile(user_id=u.id, business_name="Acme",
                        business_email=f"b{seq}@ex.com",
                        business_phone="+919876543210", business_address="1 Rd",
                        country_code="IN", state_province="MH", city="Pune",
                        postal_code="411001", gstin="27ABCDE1234F1Z5")
    db.session.add(m); db.session.flush()
    db.session.commit()
    return u, m


def _mk_category_brand():
    from models.brand import Brand
    from models.category import Category
    _SEQ[0] += 1
    seq = _SEQ[0]
    c = Category(name=f"Cat{seq}", slug=f"cat{seq}"); db.session.add(c)
    b = Brand(name=f"Br{seq}", slug=f"br{seq}"); db.session.add(b)
    db.session.flush(); db.session.commit()
    return c, b


def _create_product(app, user, category, brand, sku="NEW-1"):
    """Create through the merchant controller, as the dashboard form does."""
    from flask_jwt_extended import create_access_token
    from controllers.merchant.product_controller import MerchantProductController

    token = create_access_token(identity=str(user.id))
    with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request()
        return MerchantProductController.create({
            "category_id": category.category_id,
            "brand_id": brand.brand_id,
            "sku": sku,
            "product_name": "Widget",
            "product_description": "A widget",
            "cost_price": Decimal("500.00"),
            "selling_price": Decimal("1000.00"),
        })


def test_new_product_is_live_immediately_by_default(app):
    with app.app_context():
        app.config["FEATURE_PRODUCT_AUTO_APPROVE"] = True
        user, _ = _mk_merchant_user()
        cat, brand = _mk_category_brand()

        p = _create_product(app, user, cat, brand)

        assert p.approval_status == "approved"
        assert p.approved_at is not None
        # No human approved it, so the audit trail must not claim one did.
        assert p.approved_by is None


def test_the_gate_can_be_restored_by_config(app):
    with app.app_context():
        app.config["FEATURE_PRODUCT_AUTO_APPROVE"] = False
        user, _ = _mk_merchant_user()
        cat, brand = _mk_category_brand()

        p = _create_product(app, user, cat, brand, sku="GATED-1")

        assert p.approval_status == "pending"
        assert p.approved_at is None


def test_editing_a_live_product_does_not_pull_it_off_the_site(app):
    """Under auto-approve, a typo fix must not send the listing back to pending."""
    from controllers.merchant.product_controller import MerchantProductController
    from flask_jwt_extended import create_access_token, verify_jwt_in_request

    with app.app_context():
        app.config["FEATURE_PRODUCT_AUTO_APPROVE"] = True
        user, _ = _mk_merchant_user()
        cat, brand = _mk_category_brand()
        p = _create_product(app, user, cat, brand, sku="EDIT-1")
        pid = p.product_id

        token = create_access_token(identity=str(user.id))
        with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
            verify_jwt_in_request()
            updated = MerchantProductController.update(pid, {"product_name": "Widget v2"})

        assert updated.approval_status == "approved"


def test_with_the_gate_on_an_edit_still_requires_re_approval(app):
    """The old behaviour must survive intact for whenever it is turned back on."""
    from controllers.merchant.product_controller import MerchantProductController
    from flask_jwt_extended import create_access_token, verify_jwt_in_request

    with app.app_context():
        app.config["FEATURE_PRODUCT_AUTO_APPROVE"] = False
        user, _ = _mk_merchant_user()
        cat, brand = _mk_category_brand()
        p = _create_product(app, user, cat, brand, sku="EDIT-2")
        p.approval_status = "approved"
        db.session.commit()
        pid = p.product_id

        token = create_access_token(identity=str(user.id))
        with app.test_request_context(headers={"Authorization": f"Bearer {token}"}):
            verify_jwt_in_request()
            updated = MerchantProductController.update(pid, {"selling_price": Decimal("1200.00")})

        assert updated.approval_status == "pending"


def test_an_admin_can_still_reject_an_auto_approved_product(app):
    """Auto-approve moves the check after publication; it does not remove it."""
    from controllers.merchant.product_controller import MerchantProductController

    with app.app_context():
        app.config["FEATURE_PRODUCT_AUTO_APPROVE"] = True
        user, _ = _mk_merchant_user()
        cat, brand = _mk_category_brand()
        p = _create_product(app, user, cat, brand, sku="REJ-1")

        rejected = MerchantProductController.reject(p.product_id, admin_id=1,
                                                    reason="Misleading title")

        assert rejected.approval_status == "rejected"
        assert rejected.rejection_reason == "Misleading title"


def test_a_rejected_product_is_hidden_from_shoppers(app):
    """Rejection has to actually remove it, or the flag would be unsafe to enable.

    Public listings require approval_status == 'approved', so a rejected product
    drops out of them. This pins that, because auto-approve makes rejection the
    only barrier left.
    """
    from controllers.merchant.product_controller import MerchantProductController
    from models.product import Product

    with app.app_context():
        app.config["FEATURE_PRODUCT_AUTO_APPROVE"] = True
        user, _ = _mk_merchant_user()
        cat, brand = _mk_category_brand()
        p = _create_product(app, user, cat, brand, sku="HIDE-1")
        pid = p.product_id

        visible = Product.query.filter(
            Product.product_id == pid,
            Product.approval_status == "approved",
            Product.deleted_at.is_(None),
        ).count()
        assert visible == 1

        MerchantProductController.reject(pid, admin_id=1, reason="Prohibited")

        visible = Product.query.filter(
            Product.product_id == pid,
            Product.approval_status == "approved",
            Product.deleted_at.is_(None),
        ).count()
        assert visible == 0
