"""
User-initiated account deletion: 24h grace (configurable), then soft close.
Mirrors merchant account deletion behavior, but applies to buyer/user accounts.
"""
from datetime import datetime, timedelta, timezone

from flask import current_app

from auth.models.models import User, RefreshToken
from common.database import db


def _grace_hours():
    return int(current_app.config.get("ACCOUNT_DELETION_GRACE_HOURS", 24))


def deletion_status_for_user(user_id):
    """Return dict for GET /account/deletion-status."""
    user = User.get_by_id(user_id)
    if not user:
        return {"error": "User not found"}, 404

    now = datetime.now(timezone.utc)
    closed = user.account_deleted_at is not None
    pending = (
        not closed
        and user.account_deletion_requested_at is not None
        and user.account_deletion_effective_at is not None
    )

    effective_at = user.account_deletion_effective_at
    if effective_at and effective_at.tzinfo is None:
        effective_at = effective_at.replace(tzinfo=timezone.utc)
    elif effective_at and effective_at.tzinfo:
        effective_at = effective_at.astimezone(timezone.utc)

    return {
        "status": "closed" if closed else ("pending" if pending else "none"),
        "account_deleted_at": user.account_deleted_at.isoformat()
        if user.account_deleted_at
        else None,
        "account_deletion_requested_at": user.account_deletion_requested_at.isoformat()
        if user.account_deletion_requested_at
        else None,
        "account_deletion_effective_at": effective_at.isoformat() if effective_at else None,
        "grace_hours": _grace_hours(),
        "message": _status_message(closed, pending, effective_at, now),
    }, 200


def _status_message(closed, pending, effective_at, now):
    if closed:
        return "This account has been closed."
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
    if not user:
        return {"error": "User not found"}, 404

    if user.account_deleted_at is not None:
        return {"error": "Account is already closed"}, 410

    if user.account_deletion_requested_at and user.account_deletion_effective_at:
        eff = user.account_deletion_effective_at
        if eff and eff.tzinfo is None:
            eff = eff.replace(tzinfo=timezone.utc)
        return {
            "status": "pending",
            "account_deletion_effective_at": eff.isoformat() if eff else None,
            "message": "Deletion was already requested.",
        }, 200

    if user.password_hash:
        if not password:
            return {"error": "Password is required to delete this account"}, 400
        if not user.check_password(password):
            return {"error": "Invalid password"}, 403

    hours = _grace_hours()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    user.account_deletion_requested_at = now
    user.account_deletion_effective_at = now + timedelta(hours=hours)

    eff = user.account_deletion_effective_at
    if eff and eff.tzinfo is None:
        eff = eff.replace(tzinfo=timezone.utc)
    db.session.commit()

    return {
        "status": "pending",
        "account_deletion_requested_at": user.account_deletion_requested_at.isoformat(),
        "account_deletion_effective_at": eff.isoformat() if eff else None,
        "grace_hours": hours,
        "message": f"Account deletion scheduled. You may cancel within {hours} hours.",
    }, 200


def cancel_deletion(user_id):
    user = User.get_by_id(user_id)
    if not user:
        return {"error": "User not found"}, 404

    if user.account_deleted_at is not None:
        return {"error": "Account is already closed"}, 410

    if not user.account_deletion_requested_at:
        return {"error": "No pending deletion to cancel"}, 400

    user.account_deletion_requested_at = None
    user.account_deletion_effective_at = None
    db.session.commit()

    return {
        "status": "none",
        "message": "Account deletion has been cancelled.",
    }, 200


def finalize_user_account(user: User):
    """
    Soft-close user: set inactive, revoke refresh tokens.
    Caller must commit transaction or wrap in try/except.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    user.account_deleted_at = now
    user.is_active = False

    RefreshToken.query.filter_by(user_id=user.id, is_revoked=False).update(
        {RefreshToken.is_revoked: True}, synchronize_session=False
    )

    db.session.commit()
    current_app.logger.info("User account soft-closed: user_id=%s", user.id)


def run_finalize_due_accounts():
    """
    Process users past account_deletion_effective_at with no account_deleted_at.
    Returns dict with counts for logging.
    """
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    due = User.query.filter(
        User.account_deletion_requested_at.isnot(None),
        User.account_deletion_effective_at.isnot(None),
        User.account_deletion_effective_at <= now_naive,
        User.account_deleted_at.is_(None),
    ).all()

    finalized = 0
    errors = []
    for user in due:
        try:
            finalize_user_account(user)
            finalized += 1
        except Exception as e:
            db.session.rollback()
            errors.append(f"user_id={user.id}: {e}")
            current_app.logger.exception(
                "Failed to finalize user account deletion for user %s", user.id
            )

    return {"finalized": finalized, "errors": errors}

