from auth.twilio_service import send_otp_sms
from auth.utils import is_apple_review_test_phone, get_apple_review_fixed_otp


def test_is_apple_review_test_phone_last10_pattern():
    assert is_apple_review_test_phone("+911111122222") is True  # last10 = 1111122222
    assert is_apple_review_test_phone("+14444488888") is True  # last10 = 4444488888
    assert is_apple_review_test_phone("+910123456789") is False
    assert is_apple_review_test_phone("") is False
    assert is_apple_review_test_phone(None) is False


def test_get_apple_review_fixed_otp_fallback(app):
    with app.app_context():
        app.config["APPLE_REVIEW_OTP_CODE"] = "12-34"  # invalid length after digits-only
        assert get_apple_review_fixed_otp() == "123456"

        app.config["APPLE_REVIEW_OTP_CODE"] = "654321"
        assert get_apple_review_fixed_otp() == "654321"


def test_send_otp_sms_bypasses_twilio_for_test_numbers(app):
    with app.app_context():
        app.config["APPLE_REVIEW_OTP_BYPASS"] = True
        app.config["TWILIO_ACCOUNT_SID"] = None
        app.config["TWILIO_AUTH_TOKEN"] = None
        app.config["TWILIO_PHONE_NUMBER"] = None

        ok, msg = send_otp_sms("+911111122222", "123456")
        assert ok is True
        assert "bypass" in msg.lower()


def test_send_otp_sms_fails_without_twilio_when_not_bypassed(app):
    with app.app_context():
        app.config["APPLE_REVIEW_OTP_BYPASS"] = False
        app.config["DEV_OTP_BYPASS"] = False
        app.config["TWILIO_ACCOUNT_SID"] = None
        app.config["TWILIO_AUTH_TOKEN"] = None
        app.config["TWILIO_PHONE_NUMBER"] = None

        ok, msg = send_otp_sms("+910123456789", "123456")
        assert ok is False
        assert "not configured" in msg.lower()

