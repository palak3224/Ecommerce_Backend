"""Twilio service for sending OTP SMS messages."""
from flask import current_app
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException


def send_otp_sms(phone_number, otp_code):
    """
    Send OTP code via SMS using Twilio.
    
    Args:
        phone_number (str): Phone number in E.164 format (e.g., +1234567890)
        otp_code (str): 6-digit OTP code to send
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        account_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
        auth_token = current_app.config.get('TWILIO_AUTH_TOKEN')
        from_number = current_app.config.get('TWILIO_PHONE_NUMBER')
        
        if not all([account_sid, auth_token, from_number]):
            current_app.logger.error("Twilio credentials not configured")
            return False, "SMS service not configured"
        
        # Initialize Twilio client
        client = Client(account_sid, auth_token)
        
        # Create SMS message
        message_body = f"Your AOIN verification code is: {otp_code}. This code will expire in 10 minutes."
        
        # Send SMS
        message = client.messages.create(
            body=message_body,
            from_=from_number,
            to=phone_number
        )
        
        current_app.logger.info(f"OTP SMS sent to {phone_number}. Message SID: {message.sid}")
        return True, "OTP sent successfully"
        
    except TwilioRestException as e:
        current_app.logger.error(f"Twilio error sending SMS to {phone_number}: {str(e)}")
        return False, f"Failed to send SMS: {str(e)}"
    except Exception as e:
        current_app.logger.error(f"Unexpected error sending SMS to {phone_number}: {str(e)}")
        return False, f"Failed to send SMS: {str(e)}"

