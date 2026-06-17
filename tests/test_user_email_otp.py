"""HTTP-level tests for app-based customer (buyer) email-OTP verification.

Mirrors the merchant OTP tests: register with source="app" -> OTP email -> verify;
web link regression; unknown-field guard; resend throttle. Email sending is patched.
"""
import pytest
from unittest.mock import patch

from app import create_app
from common.database import db


@pytest.fixture
def app():
    application = create_app("testing")
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


def _user_payload(**overrides):
    data = {
        "email": "buyer@example.com",
        "password": "StrongPass123",
        "first_name": "Bob",
        "last_name": "Buyer",
    }
    data.update(overrides)
    return data


def test_app_register_sends_otp_and_verifies(client):
    with patch("auth.controllers.send_verification_email_otp", return_value=True) as otp_mail, \
         patch("auth.controllers.send_verification_email", return_value=True) as link_mail:
        resp = client.post("/api/auth/register", json=_user_payload(source="app"))
        assert resp.status_code == 201, resp.get_json()
        body = resp.get_json()
        assert body["verification_method"] == "otp"
        assert "dev_otp" in body
        otp = body["dev_otp"]
        assert otp_mail.called and not link_mail.called

        bad = client.post("/api/auth/verify-email-otp",
                          json={"email": "buyer@example.com", "otp": "000000"})
        assert bad.status_code == 400

        ok = client.post("/api/auth/verify-email-otp",
                         json={"email": "buyer@example.com", "otp": otp})
        assert ok.status_code == 200, ok.get_json()
        data = ok.get_json()
        assert "access_token" in data and "refresh_token" in data
        assert data["user"]["is_email_verified"] is True
        assert data["user"]["role"] == "user"


def test_app_verify_is_idempotent(client):
    with patch("auth.controllers.send_verification_email_otp", return_value=True), \
         patch("auth.controllers.send_verification_email", return_value=True):
        otp = client.post("/api/auth/register", json=_user_payload(source="app")).get_json()["dev_otp"]
        assert client.post("/api/auth/verify-email-otp",
                           json={"email": "buyer@example.com", "otp": otp}).status_code == 200
        assert client.post("/api/auth/verify-email-otp",
                           json={"email": "buyer@example.com", "otp": otp}).status_code == 200


def test_short_otp_is_validation_error(client):
    resp = client.post("/api/auth/verify-email-otp",
                       json={"email": "buyer@example.com", "otp": "123"})
    assert resp.status_code == 400


def test_web_register_uses_link_not_otp(client):
    with patch("auth.controllers.send_verification_email_otp", return_value=True) as otp_mail, \
         patch("auth.controllers.send_verification_email", return_value=True) as link_mail:
        resp = client.post("/api/auth/register", json=_user_payload())
        assert resp.status_code == 201, resp.get_json()
        body = resp.get_json()
        assert body["verification_method"] == "link"
        assert "dev_otp" not in body
        assert link_mail.called and not otp_mail.called

        from auth.models.models import User, EmailVerification
        user = User.get_by_email("buyer@example.com")
        row = EmailVerification.query.filter_by(user_id=user.id).first()
        assert row is not None and row.otp is None


def test_unknown_field_is_rejected(client):
    resp = client.post("/api/auth/register", json=_user_payload(totally_unknown="x"))
    assert resp.status_code == 400


def test_bad_source_is_rejected(client):
    resp = client.post("/api/auth/register", json=_user_payload(source="banana"))
    assert resp.status_code == 400


def test_resend_throttled_within_30s(client):
    with patch("auth.controllers.send_verification_email_otp", return_value=True), \
         patch("auth.controllers.send_verification_email", return_value=True):
        client.post("/api/auth/register", json=_user_payload(source="app"))
        resp = client.post("/api/auth/resend-email-otp", json={"email": "buyer@example.com"})
        assert resp.status_code == 429


def test_resend_unknown_email_is_generic_200(client):
    resp = client.post("/api/auth/resend-email-otp", json={"email": "nobody@nowhere.com"})
    assert resp.status_code == 200


def test_merchant_cannot_use_user_otp_verify(client):
    # A merchant account should be rejected by the customer OTP verify endpoint.
    with patch("auth.controllers.send_verification_email_otp", return_value=True), \
         patch("auth.controllers.send_verification_email", return_value=True):
        merchant = {
            "password": "StrongPass123", "first_name": "M", "last_name": "X",
            "business_name": "MX", "business_email": "mx@example.com",
            "business_phone": "+919876543210", "business_address": "addr",
            "country_code": "IN", "state_province": "MH", "city": "Pune", "postal_code": "411001",
            "source": "app",
        }
        otp = client.post("/api/auth/register/merchant", json=merchant).get_json()["dev_otp"]
        # Wrong endpoint for a merchant -> 403
        resp = client.post("/api/auth/verify-email-otp",
                           json={"email": "mx@example.com", "otp": otp})
        assert resp.status_code == 403
