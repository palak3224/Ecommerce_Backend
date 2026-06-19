"""Tests for editing phone on PUT /api/users/profile (no OTP, uniqueness-guarded)."""
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


def _mk_user(email, phone=None):
    from auth.models.models import User, UserRole
    u = User(email=email, first_name="A", last_name="B", role=UserRole.USER,
             is_email_verified=True, phone=phone)
    u.set_password("StrongPass123")
    db.session.add(u)
    db.session.flush()
    return u


def _auth(user_id):
    from flask_jwt_extended import create_access_token
    from auth.models.models import UserRole
    tok = create_access_token(identity=str(user_id), additional_claims={"role": UserRole.USER.value})
    return {"Authorization": f"Bearer {tok}"}


def test_phone_update_saves(client, app):
    with app.app_context():
        u = _mk_user("buyer@ex.com")
        db.session.commit()
        uid = u.id
    resp = client.put("/api/users/profile",
                      json={"first_name": "Palak", "last_name": "Tiwari", "phone": "9171453224"},
                      headers=_auth(uid))
    assert resp.status_code == 200, resp.get_json()
    assert resp.get_json()["profile"]["phone"] == "9171453224"
    with app.app_context():
        from auth.models.models import User
        assert User.get_by_id(uid).phone == "9171453224"


def test_phone_duplicate_rejected(client, app):
    with app.app_context():
        _mk_user("owner@ex.com", phone="9171453224")  # already owns this phone
        me = _mk_user("me@ex.com")
        db.session.commit()
        my_id = me.id
    resp = client.put("/api/users/profile",
                      json={"phone": "9171453224"},
                      headers=_auth(my_id))
    assert resp.status_code == 409


def test_phone_can_be_cleared(client, app):
    with app.app_context():
        u = _mk_user("clear@ex.com", phone="9171453224")
        db.session.commit()
        uid = u.id
    resp = client.put("/api/users/profile", json={"phone": None}, headers=_auth(uid))
    assert resp.status_code == 200
    with app.app_context():
        from auth.models.models import User
        assert User.get_by_id(uid).phone is None


def test_phone_alphabets_rejected(client, app):
    with app.app_context():
        u = _mk_user("bad@ex.com")
        db.session.commit()
        uid = u.id
    resp = client.put("/api/users/profile", json={"phone": "abcd123"}, headers=_auth(uid))
    assert resp.status_code == 400


def test_same_phone_no_self_conflict(client, app):
    # Re-saving your own existing phone must not 409 against yourself.
    with app.app_context():
        u = _mk_user("self@ex.com", phone="9171453224")
        db.session.commit()
        uid = u.id
    resp = client.put("/api/users/profile",
                      json={"first_name": "X", "phone": "9171453224"},
                      headers=_auth(uid))
    assert resp.status_code == 200


def test_other_fields_still_work(client, app):
    with app.app_context():
        u = _mk_user("fields@ex.com")
        db.session.commit()
        uid = u.id
    resp = client.put("/api/users/profile",
                      json={"first_name": "New", "last_name": "Name", "gender": "female"},
                      headers=_auth(uid))
    assert resp.status_code == 200
    body = resp.get_json()["profile"]
    assert body["first_name"] == "New" and body["gender"] == "female"
