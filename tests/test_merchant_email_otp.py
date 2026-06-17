"""HTTP-level tests for app-based merchant email-OTP verification.

Covers the full app onboarding branch (register with source="app" -> OTP email ->
verify OTP), the web link regression (no source -> link, NULL otp), resend
throttling, and the unknown-field guard. Email sending is patched so nothing is
actually sent; DEV_OTP_BYPASS echoes the OTP in the response for assertions.
"""
import pytest
from unittest.mock import patch

from app import create_app
from common.database import db


@pytest.fixture
def app():
    application = create_app("testing")
    # Echo OTPs in responses and make the "mail configured" check pass so the
    # send branch runs (the sender itself is patched in each test).
    application.config["DEV_OTP_BYPASS"] = True
    application.config["MAIL_SERVER"] = "smtp.test"
    application.config["MAIL_USERNAME"] = "u"
    application.config["MAIL_PASSWORD"] = "p"
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _merchant_payload(**overrides):
    data = {
        "password": "StrongPass123",
        "first_name": "Asha",
        "last_name": "Verma",
        "business_name": "Asha Crafts",
        "business_email": "seller@ashacrafts.com",
        "business_phone": "+91 9876543210",
        "business_address": "12 MG Road",
        "country_code": "IN",
        "state_province": "MH",
        "city": "Pune",
        "postal_code": "411001",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------- app OTP flow

def test_app_register_sends_otp_and_verifies(client):
    with patch("auth.controllers.send_verification_email_otp", return_value=True) as otp_mail, \
         patch("auth.controllers.send_verification_email", return_value=True) as link_mail:

        # Register from the app
        resp = client.post("/api/auth/register/merchant",
                           json=_merchant_payload(source="app"))
        assert resp.status_code == 201, resp.get_json()
        body = resp.get_json()
        assert body["verification_method"] == "otp"
        assert "dev_otp" in body                 # echoed because DEV_OTP_BYPASS
        otp = body["dev_otp"]
        assert otp_mail.called and not link_mail.called

        # Wrong OTP is rejected
        bad = client.post("/api/auth/merchant/verify-email-otp",
                          json={"email": "seller@ashacrafts.com", "otp": "000000"})
        assert bad.status_code == 400

        # Correct OTP verifies and returns a session
        ok = client.post("/api/auth/merchant/verify-email-otp",
                         json={"email": "seller@ashacrafts.com", "otp": otp})
        assert ok.status_code == 200, ok.get_json()
        data = ok.get_json()
        assert "access_token" in data and "refresh_token" in data
        assert "merchant" in data
        assert data["user"]["is_email_verified"] is True
        assert data["merchant"]["verification_status"] == "email_verified"


def test_app_verify_is_idempotent(client):
    with patch("auth.controllers.send_verification_email_otp", return_value=True), \
         patch("auth.controllers.send_verification_email", return_value=True):
        resp = client.post("/api/auth/register/merchant",
                           json=_merchant_payload(source="app"))
        otp = resp.get_json()["dev_otp"]
        first = client.post("/api/auth/merchant/verify-email-otp",
                            json={"email": "seller@ashacrafts.com", "otp": otp})
        assert first.status_code == 200
        # Re-verifying an already-verified account is a no-op success
        again = client.post("/api/auth/merchant/verify-email-otp",
                            json={"email": "seller@ashacrafts.com", "otp": otp})
        assert again.status_code == 200


def test_short_otp_is_validation_error(client):
    resp = client.post("/api/auth/merchant/verify-email-otp",
                       json={"email": "seller@ashacrafts.com", "otp": "123"})
    assert resp.status_code == 400


# ---------------------------------------------------------------- web regression

def test_web_register_uses_link_not_otp(client):
    with patch("auth.controllers.send_verification_email_otp", return_value=True) as otp_mail, \
         patch("auth.controllers.send_verification_email", return_value=True) as link_mail:
        resp = client.post("/api/auth/register/merchant", json=_merchant_payload())
        assert resp.status_code == 201, resp.get_json()
        body = resp.get_json()
        assert body["verification_method"] == "link"
        assert "dev_otp" not in body
        assert link_mail.called and not otp_mail.called

        # The verification row for a web merchant has no OTP set
        from auth.models.models import User, EmailVerification
        user = User.get_by_email("seller@ashacrafts.com")
        row = EmailVerification.query.filter_by(user_id=user.id).first()
        assert row is not None and row.otp is None


def test_unknown_field_is_rejected(client):
    # marshmallow defaults to RAISE; an undeclared field must 400 (proves why
    # `source` had to be declared in the schema).
    resp = client.post("/api/auth/register/merchant",
                       json=_merchant_payload(totally_unknown="x"))
    assert resp.status_code == 400


def test_bad_source_is_rejected(client):
    resp = client.post("/api/auth/register/merchant",
                       json=_merchant_payload(source="banana"))
    assert resp.status_code == 400


# ---------------------------------------------------------------- resend

def test_resend_throttled_within_30s(client):
    with patch("auth.controllers.send_verification_email_otp", return_value=True), \
         patch("auth.controllers.send_verification_email", return_value=True):
        client.post("/api/auth/register/merchant",
                    json=_merchant_payload(source="app"))
        # OTP just created at registration -> immediate resend hits the 30s DB guard
        resp = client.post("/api/auth/merchant/resend-email-otp",
                           json={"email": "seller@ashacrafts.com"})
        assert resp.status_code == 429


def test_resend_unknown_email_is_generic_200(client):
    # No account -> generic success (no email enumeration)
    resp = client.post("/api/auth/merchant/resend-email-otp",
                       json={"email": "nobody@nowhere.com"})
    assert resp.status_code == 200


def test_resend_already_verified_is_200(client):
    with patch("auth.controllers.send_verification_email_otp", return_value=True), \
         patch("auth.controllers.send_verification_email", return_value=True):
        resp = client.post("/api/auth/register/merchant",
                           json=_merchant_payload(source="app"))
        otp = resp.get_json()["dev_otp"]
        client.post("/api/auth/merchant/verify-email-otp",
                    json={"email": "seller@ashacrafts.com", "otp": otp})
        done = client.post("/api/auth/merchant/resend-email-otp",
                           json={"email": "seller@ashacrafts.com"})
        assert done.status_code == 200
