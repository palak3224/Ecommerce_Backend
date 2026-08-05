"""
Merchant-initiated account deletion: 24h grace (configurable), then soft close.
"""
from datetime import datetime, timedelta, timezone

from flask import current_app

from auth.models.models import MerchantProfile, User, RefreshToken
from common.database import db
from models.product import Product
from models.reel import Reel
from models.merchant_intro_video import MerchantIntroVideo
from models.live_stream import LiveStream


def _grace_hours():
    return int(current_app.config.get("ACCOUNT_DELETION_GRACE_HOURS", 24))


def deletion_status_for_user(user_id):
    """Return dict for GET /account/deletion-status."""
    profile = MerchantProfile.get_by_user_id(user_id)
    if not profile:
        return {"error": "Merchant profile not found"}, 404

    now = datetime.now(timezone.utc)
    closed = profile.account_deleted_at is not None
    pending = (
        not closed
        and profile.account_deletion_requested_at is not None
        and profile.account_deletion_effective_at is not None
    )

    effective_at = profile.account_deletion_effective_at
    if effective_at and effective_at.tzinfo is None:
        effective_at = effective_at.replace(tzinfo=timezone.utc)
    elif effective_at and effective_at.tzinfo:
        effective_at = effective_at.astimezone(timezone.utc)

    return {
        "status": "closed" if closed else ("pending" if pending else "none"),
        "account_deleted_at": profile.account_deleted_at.isoformat()
        if profile.account_deleted_at
        else None,
        "account_deletion_requested_at": profile.account_deletion_requested_at.isoformat()
        if profile.account_deletion_requested_at
        else None,
        "account_deletion_effective_at": effective_at.isoformat()
        if effective_at
        else None,
        "grace_hours": _grace_hours(),
        "message": _status_message(closed, pending, effective_at, now),
    }, 200


def _status_message(closed, pending, effective_at, now):
    if closed:
        return "This merchant account has been closed."
    if pending and effective_at:
        if effective_at > now:
            return "Account deletion is scheduled. You can cancel before the effective time."
        return "Account deletion is being finalized."
    return "No deletion scheduled."


def request_deletion(user_id, password=None):
    """
    Start deletion grace window. Optional password when user has password_hash.
    Returns (body_dict, http_status).
    """
    user = User.get_by_id(user_id)
    profile = MerchantProfile.get_by_user_id(user_id)
    if not user or not profile:
        return {"error": "Merchant profile not found"}, 404

    if profile.account_deleted_at is not None:
        return {"error": "Account is already closed"}, 410

    if profile.account_deletion_requested_at and profile.account_deletion_effective_at:
        eff = profile.account_deletion_effective_at
        if eff.tzinfo is None:
            eff = eff.replace(tzinfo=timezone.utc)
        return {
            "status": "pending",
            "account_deletion_effective_at": eff.isoformat(),
            "message": "Deletion was already requested.",
        }, 200

    if user.password_hash:
        if not password:
            return {"error": "Password is required to delete this account"}, 400
        if not user.check_password(password):
            return {"error": "Invalid password"}, 403

    hours = _grace_hours()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    profile.account_deletion_requested_at = now
    profile.account_deletion_effective_at = now + timedelta(hours=hours)

    eff = profile.account_deletion_effective_at
    if eff and eff.tzinfo is None:
        eff = eff.replace(tzinfo=timezone.utc)
    db.session.commit()

    return {
        "status": "pending",
        "account_deletion_requested_at": profile.account_deletion_requested_at.isoformat(),
        "account_deletion_effective_at": eff.isoformat() if eff else None,
        "grace_hours": hours,
        "message": f"Account deletion scheduled. You may cancel within {hours} hours.",
    }, 200


def cancel_deletion(user_id):
    profile = MerchantProfile.get_by_user_id(user_id)
    if not profile:
        return {"error": "Merchant profile not found"}, 404

    if profile.account_deleted_at is not None:
        return {"error": "Account is already closed"}, 410

    if not profile.account_deletion_requested_at:
        return {"error": "No pending deletion to cancel"}, 400

    profile.account_deletion_requested_at = None
    profile.account_deletion_effective_at = None
    db.session.commit()

    return {
        "status": "none",
        "message": "Account deletion has been cancelled.",
    }, 200


def finalize_merchant_profile(profile: MerchantProfile):
    """
    Soft-close merchant: user inactive, revoke refresh tokens, hide products/reels/streams.
    Caller must commit transaction or wrap in try/except.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user = User.get_by_id(profile.user_id)
    if not user:
        return

    profile.account_deleted_at = now
    user.is_active = False

    RefreshToken.query.filter_by(user_id=user.id, is_revoked=False).update(
        {RefreshToken.is_revoked: True}, synchronize_session=False
    )

    Product.query.filter(
        Product.merchant_id == profile.id,
        Product.deleted_at.is_(None),
    ).update(
        {
            Product.deleted_at: now,
            Product.active_flag: False,
        },
        synchronize_session=False,
    )

    Reel.query.filter(
        Reel.merchant_id == profile.id,
        Reel.deleted_at.is_(None),
    ).update(
        {
            Reel.deleted_at: now,
            Reel.is_active: False,
        },
        synchronize_session=False,
    )

    LiveStream.query.filter(
        LiveStream.merchant_id == profile.id,
        LiveStream.deleted_at.is_(None),
    ).update({LiveStream.deleted_at: now}, synchronize_session=False)

    # Soft-delete the intro video too. The S3 objects are left to the purge job
    # rather than deleted here — this sweep runs in a scheduler and must not
    # block on network calls to AWS.
    MerchantIntroVideo.query.filter(
        MerchantIntroVideo.merchant_id == profile.id,
        MerchantIntroVideo.deleted_at.is_(None),
    ).update(
        {
            MerchantIntroVideo.deleted_at: now,
            MerchantIntroVideo.is_active: False,
        },
        synchronize_session=False,
    )

    db.session.commit()
    current_app.logger.info(
        "Merchant account soft-closed: merchant_profile_id=%s user_id=%s",
        profile.id,
        user.id,
    )


def run_finalize_due_accounts():
    """
    Process merchants past account_deletion_effective_at with no account_deleted_at.
    Returns dict with counts for logging.
    """
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    due = MerchantProfile.query.filter(
        MerchantProfile.account_deletion_requested_at.isnot(None),
        MerchantProfile.account_deletion_effective_at.isnot(None),
        MerchantProfile.account_deletion_effective_at <= now_naive,
        MerchantProfile.account_deleted_at.is_(None),
    ).all()

    finalized = 0
    errors = []
    for profile in due:
        try:
            finalize_merchant_profile(profile)
            finalized += 1
        except Exception as e:
            db.session.rollback()
            errors.append(f"merchant_profile_id={profile.id}: {e}")
            current_app.logger.exception(
                "Failed to finalize merchant account deletion for profile %s", profile.id
            )

    return {"finalized": finalized, "errors": errors}
