"""Tests for the merchant public bio on GET/PUT /api/merchants/profile."""
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


def _mk_merchant(email="merchant@ex.com"):
    from auth.models.models import User, UserRole, MerchantProfile

    user = User(email=email, first_name="M", last_name="P", role=UserRole.MERCHANT,
                is_email_verified=True)
    user.set_password("StrongPass123")
    db.session.add(user)
    db.session.flush()

    profile = MerchantProfile(
        user_id=user.id,
        business_name="Brass Works",
        business_email=email,
        business_phone="9990001111",
        business_address="1 Main St",
        country_code="IN",
        state_province="UP",
        city="Moradabad",
        postal_code="244001",
    )
    db.session.add(profile)
    db.session.flush()
    return user, profile


def _auth(user_id):
    from flask_jwt_extended import create_access_token
    from auth.models.models import UserRole

    token = create_access_token(
        identity=str(user_id), additional_claims={"role": UserRole.MERCHANT.value}
    )
    return {"Authorization": f"Bearer {token}"}


def test_bio_saves_and_reads_back(client, app):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.put(
        "/api/merchants/profile",
        json={"bio": "Handmade brass decor.\nShips worldwide."},
        headers=_auth(uid),
    )
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["profile"]["bio"] == "Handmade brass decor.\nShips worldwide."

    resp = client.get("/api/merchants/profile", headers=_auth(uid))
    assert resp.get_json()["profile"]["bio"] == "Handmade brass decor.\nShips worldwide."


def test_bio_over_limit_rejected(client, app):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.put("/api/merchants/profile", json={"bio": "x" * 251}, headers=_auth(uid))
    assert resp.status_code == 400
    assert "bio" in resp.get_json()["details"]


def test_bio_too_many_lines_rejected(client, app):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.put(
        "/api/merchants/profile", json={"bio": "a\nb\nc\nd\ne\nf"}, headers=_auth(uid)
    )
    assert resp.status_code == 400
    assert "bio" in resp.get_json()["details"]


def test_bio_strips_html_and_zero_width(client, app):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    # ​ is a zero-width space — invisible, and a classic way to slip
    # lookalike text past a reviewer.
    resp = client.put(
        "/api/merchants/profile",
        json={"bio": "<script>alert(1)</script>Hello​there"},
        headers=_auth(uid),
    )
    assert resp.status_code == 200
    # Tags stripped, zero-width space removed, inner text kept as plain text.
    assert resp.get_json()["profile"]["bio"] == "alert(1)Hellothere"


def test_bio_can_be_cleared(client, app):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    client.put("/api/merchants/profile", json={"bio": "Something"}, headers=_auth(uid))
    resp = client.put("/api/merchants/profile", json={"bio": ""}, headers=_auth(uid))
    assert resp.status_code == 200
    assert resp.get_json()["profile"]["bio"] is None


def test_bio_absent_key_leaves_value_untouched(client, app):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    client.put("/api/merchants/profile", json={"bio": "Keep me"}, headers=_auth(uid))
    resp = client.put(
        "/api/merchants/profile", json={"business_name": "Brass Works II"}, headers=_auth(uid)
    )
    assert resp.status_code == 200
    assert resp.get_json()["profile"]["bio"] == "Keep me"


@pytest.mark.parametrize(
    "bad_link",
    ["javascript:alert(1)", "data:text/html;base64,PHN2Zz4=", "vbscript:msgbox(1)"],
)
def test_bio_link_dangerous_schemes_rejected(client, app, bad_link):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.put("/api/merchants/profile", json={"bio_link": bad_link}, headers=_auth(uid))
    assert resp.status_code == 400
    assert "bio_link" in resp.get_json()["details"]


def test_bio_link_gets_https_prefix(client, app):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.put(
        "/api/merchants/profile", json={"bio_link": "example.com/shop"}, headers=_auth(uid)
    )
    assert resp.status_code == 200
    assert resp.get_json()["profile"]["bio_link"] == "https://example.com/shop"


def test_link_label_dropped_without_link(client, app):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.put(
        "/api/merchants/profile", json={"bio_link_label": "Catalogue"}, headers=_auth(uid)
    )
    assert resp.status_code == 200
    assert resp.get_json()["profile"]["bio_link_label"] is None


def test_bio_appears_on_public_profile(client, app):
    with app.app_context():
        user, profile = _mk_merchant()
        db.session.commit()
        uid, mid = user.id, profile.id

    client.put("/api/merchants/profile", json={"bio": "Public hello"}, headers=_auth(uid))
    resp = client.get(f"/api/merchants/{mid}/public-profile")
    assert resp.status_code == 200
    assert resp.get_json()["bio"] == "Public hello"


def test_public_profile_hidden_for_inactive_user(client, app):
    with app.app_context():
        user, profile = _mk_merchant()
        db.session.commit()
        uid, mid = user.id, profile.id

    client.put("/api/merchants/profile", json={"bio": "Public hello"}, headers=_auth(uid))

    with app.app_context():
        from auth.models.models import User

        suspended = User.get_by_id(uid)
        suspended.is_active = False
        db.session.commit()

    resp = client.get(f"/api/merchants/{mid}/public-profile")
    assert resp.status_code == 404


def test_business_phone_still_rejected(client, app):
    # Guards the Phase 0 fix: the frontend must not send this key.
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.put(
        "/api/merchants/profile", json={"business_phone": "9998887777"}, headers=_auth(uid)
    )
    assert resp.status_code == 400
