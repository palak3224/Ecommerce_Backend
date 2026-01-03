import os
import datetime
import requests
from sqlalchemy.orm import Session
from fastapi import Request
from models.youtube_token import YouTubeToken
from common.database import db
from apscheduler.schedulers.background import BackgroundScheduler
import threading

# You may want to use environment variables for these
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
YOUTUBE_REDIRECT_URI = os.getenv("YOUTUBE_REDIRECT_URI")

YOUTUBE_OAUTH_URL = (
    "https://accounts.google.com/o/oauth2/v2/auth?"
    "client_id={client_id}&"
    "redirect_uri={redirect_uri}&"
    "response_type=code&"
    "scope=https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/youtube.force-ssl&"
    "access_type=offline&"
    "prompt=consent"
)


def get_token_record():
    return YouTubeToken.query.order_by(YouTubeToken.id.desc()).first()


def configure_youtube():
    url = YOUTUBE_OAUTH_URL.format(
        client_id=YOUTUBE_CLIENT_ID,
        redirect_uri=YOUTUBE_REDIRECT_URI
    )
    return {"oauth_url": url}


def handle_oauth_callback(code: str):
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "redirect_uri": YOUTUBE_REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    try:
        resp = requests.post(token_url, data=data, timeout=10)
    except requests.exceptions.Timeout:
        return {"error": "Failed to get tokens from Google", "details": "Request timed out after 10 seconds"}
    except requests.exceptions.RequestException as e:
        return {"error": "Failed to get tokens from Google", "details": str(e)}
    if resp.status_code != 200:
        return {"error": "Failed to get tokens from Google", "details": resp.text}
    token_data = resp.json()
    expires_in = token_data.get("expires_in", 3600)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
    # Deactivate old tokens
    YouTubeToken.query.update({YouTubeToken.is_active: False})
    db.session.commit()
    # Save new token
    token = YouTubeToken(
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token", ""),
        token_type=token_data["token_type"],
        expires_at=expires_at,
        is_active=True
    )
    db.session.add(token)
    db.session.commit()
    return {"message": "YouTube token saved successfully"}


def get_status():
    token = get_token_record()
    if not token or not token.is_active:
        return {"status": "no_token", "message": "YouTube integration not configured."}
    now = datetime.datetime.utcnow()
    days_until_expiry = (token.expires_at - now).days
    if token.expires_at < now:
        status = "expired"
        message = "YouTube token has expired. Please refresh or reconfigure."
    elif days_until_expiry < 7:
        status = "expiring_soon"
        message = f"Token expiring in {days_until_expiry} days. Please refresh soon."
    else:
        status = "active"
        message = "YouTube integration is active."
    return {
        "status": status,
        "message": message,
        "token_info": {
            "id": token.id,
            "token_type": token.token_type,
            "expires_at": token.expires_at.isoformat(),
            "is_active": token.is_active,
            "created_at": token.created_at.isoformat(),
            "updated_at": token.updated_at.isoformat(),
            "days_until_expiry": days_until_expiry
        }
    }


def refresh_token():
    token = get_token_record()
    if not token or not token.refresh_token:
        return {"error": "No refresh token available."}
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": token.refresh_token,
        "grant_type": "refresh_token"
    }
    try:
        resp = requests.post(token_url, data=data, timeout=10)
    except requests.exceptions.Timeout:
        return {"error": "Failed to refresh token", "details": "Request timed out after 10 seconds"}
    except requests.exceptions.RequestException as e:
        return {"error": "Failed to refresh token", "details": str(e)}
    if resp.status_code != 200:
        return {"error": "Failed to refresh token", "details": resp.text}
    token_data = resp.json()
    expires_in = token_data.get("expires_in", 3600)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)
    token.access_token = token_data["access_token"]
    token.expires_at = expires_at
    token.updated_at = datetime.datetime.utcnow()
    db.session.commit()
    return {"message": "Token refreshed successfully"}


def revoke_token():
    token = get_token_record()
    if not token:
        return {"error": "No token to revoke."}
    # Optionally call Google's revoke endpoint
    revoke_url = f"https://oauth2.googleapis.com/revoke?token={token.access_token}"
    try:
        requests.post(revoke_url, timeout=10)
    except (requests.exceptions.Timeout, requests.exceptions.RequestException) as e:
        # Log but don't fail - token will still be deactivated locally
        print(f"Warning: Failed to revoke token at Google: {str(e)}")
    token.is_active = False
    db.session.commit()
    return {"message": "Token revoked and deactivated."}


def test_connection():
    token = get_token_record()
    if not token or not token.is_active:
        return {"status": "error", "message": "No active token."}
    headers = {"Authorization": f"Bearer {token.access_token}"}
    try:
        resp = requests.get("https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true", headers=headers, timeout=10)
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "Request timed out after 10 seconds"}
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e)}
    if resp.status_code == 200:
        data = resp.json()
        channel_info = data["items"][0]["snippet"] if data.get("items") else {}
        return {
            "status": "connected",
            "channel_info": {
                "channel_name": channel_info.get("title"),
                "description": channel_info.get("description")
            }
        }
    else:
        return {"status": "error", "message": resp.text}


def auto_refresh_youtube_token():
    """
    Checks if the YouTube token is expiring soon (less than 1 day left).
    If so, refreshes the token automatically.
    This function is intended to be run by a scheduler.
    """
    token = get_token_record()
    if token and token.is_active:
        time_left = (token.expires_at - datetime.datetime.utcnow()).total_seconds()
        if time_left < 24 * 3600:  # less than 1 day
            print("[YouTube Scheduler] Token is expiring soon. Refreshing...")
            result = refresh_token()
            print(f"[YouTube Scheduler] Refresh result: {result}")
        else:
            print(f"[YouTube Scheduler] Token is valid for another {time_left/3600:.2f} hours.")
    else:
        print("[YouTube Scheduler] No active token found. Skipping refresh.")

# Scheduler instance (to be started from app.py)
scheduler = BackgroundScheduler()

def start_youtube_token_scheduler():
    """
    Call this function ONCE from your app startup (e.g., in app.py) to start the scheduler.
    """
    if not scheduler.running:
        scheduler.add_job(auto_refresh_youtube_token, 'interval', hours=1, id='youtube_token_refresh')
        # Use a thread to avoid blocking the main app
        threading.Thread(target=scheduler.start, daemon=True).start()
        print("[YouTube Scheduler] Started background scheduler for YouTube token refresh.") 