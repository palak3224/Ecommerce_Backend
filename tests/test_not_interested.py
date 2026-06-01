"""Tests for per-user reel 'not interested' preferences (vendor block + category hide).

Verifies the feed-filtering behaviour at the model layer (get_visible_reels) and
that the preferences are strictly user-scoped.
"""
import pytest

from app import create_app
from common.database import db


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _make_user(email):
    from auth.models.models import User, UserRole
    user = User(email=email, first_name="T", last_name="U", role=UserRole.USER, is_email_verified=True)
    user.set_password("pw")
    db.session.add(user)
    db.session.flush()
    return user


def _make_merchant(user):
    from auth.models.models import MerchantProfile
    m = MerchantProfile(
        user_id=user.id,
        business_name=f"Biz {user.id}",
        business_email=f"biz{user.id}@example.com",
        business_phone="0000000000",
        business_address="addr",
        state_province="ST",
        city="City",
        postal_code="00000",
    )
    db.session.add(m)
    db.session.flush()
    return m


def _make_category(name):
    from models.category import Category
    c = Category(name=name, slug=name.lower())
    db.session.add(c)
    db.session.flush()
    return c


def _make_external_reel(merchant, category):
    """External reel (no product) so visibility only needs reel-level fields + product_url."""
    from models.reel import Reel
    r = Reel(
        merchant_id=merchant.id,
        product_id=None,
        product_url="https://example.com/p",
        product_name="X",
        category_id=category.category_id,
        category_name=category.name,
        platform="other",
        video_url="https://example.com/v.mp4",
        description="d",
        is_active=True,
    )
    db.session.add(r)
    db.session.flush()
    return r


def test_block_vendor_hides_only_for_that_user(app_ctx):
    from models.reel import Reel
    from models.user_blocked_merchant import UserBlockedMerchant

    seller_owner = _make_user("seller@example.com")
    merchant = _make_merchant(seller_owner)
    cat = _make_category("Shoes")
    reel = _make_external_reel(merchant, cat)

    blocker = _make_user("blocker@example.com")
    other = _make_user("other@example.com")
    db.session.commit()

    # Visible to everyone before blocking
    assert reel.reel_id in {r.reel_id for r in Reel.get_visible_reels().all()}
    assert reel.reel_id in {r.reel_id for r in Reel.get_visible_reels(user_id=blocker.id).all()}

    # Block for `blocker` only
    UserBlockedMerchant.block(blocker.id, merchant.id)
    db.session.commit()

    blocker_ids = {r.reel_id for r in Reel.get_visible_reels(user_id=blocker.id).all()}
    other_ids = {r.reel_id for r in Reel.get_visible_reels(user_id=other.id).all()}
    anon_ids = {r.reel_id for r in Reel.get_visible_reels().all()}

    assert reel.reel_id not in blocker_ids       # hidden for the blocker
    assert reel.reel_id in other_ids             # still visible to others
    assert reel.reel_id in anon_ids              # still visible anonymously

    # Unblock restores it
    UserBlockedMerchant.unblock(blocker.id, merchant.id)
    db.session.commit()
    assert reel.reel_id in {r.reel_id for r in Reel.get_visible_reels(user_id=blocker.id).all()}


def test_hide_category_hides_external_reel(app_ctx):
    from models.reel import Reel
    from models.user_hidden_category import UserHiddenCategory

    owner = _make_user("seller2@example.com")
    merchant = _make_merchant(owner)
    cat = _make_category("Electronics")
    other_cat = _make_category("Books")
    reel = _make_external_reel(merchant, cat)

    user = _make_user("hider@example.com")
    db.session.commit()

    assert reel.reel_id in {r.reel_id for r in Reel.get_visible_reels(user_id=user.id).all()}

    UserHiddenCategory.hide(user.id, cat.category_id)
    db.session.commit()
    assert reel.reel_id not in {r.reel_id for r in Reel.get_visible_reels(user_id=user.id).all()}

    # Hiding a different category does not affect this reel
    UserHiddenCategory.unhide(user.id, cat.category_id)
    UserHiddenCategory.hide(user.id, other_cat.category_id)
    db.session.commit()
    assert reel.reel_id in {r.reel_id for r in Reel.get_visible_reels(user_id=user.id).all()}


def test_block_auto_unfollows_via_endpoint(app_ctx):
    from models.user_merchant_follow import UserMerchantFollow
    from models.user_blocked_merchant import UserBlockedMerchant
    from controllers.user_preference_controller import UserPreferenceController
    from flask_jwt_extended import create_access_token

    owner = _make_user("seller3@example.com")
    merchant = _make_merchant(owner)
    follower = _make_user("follower@example.com")
    UserMerchantFollow.follow(follower.id, merchant.id)
    db.session.commit()

    assert UserMerchantFollow.is_following(follower.id, merchant.id)

    # Call controller within a request context carrying the follower's identity
    token = create_access_token(identity=str(follower.id))
    with app_ctx.test_request_context(headers={"Authorization": f"Bearer {token}"}):
        from flask_jwt_extended import verify_jwt_in_request
        verify_jwt_in_request()
        resp, status = UserPreferenceController.block_merchant(merchant.id)

    assert status == 201
    assert UserBlockedMerchant.is_blocked(follower.id, merchant.id)
    assert not UserMerchantFollow.is_following(follower.id, merchant.id)  # auto-unfollowed
