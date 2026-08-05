"""
Purge job for soft-deleted merchant intro videos.

Two things accumulate otherwise:
  - rows soft-deleted by the merchant or by the account-deletion sweep
  - S3 objects orphaned when a replace succeeded but the follow-up delete failed

Both are cheap to leave around briefly and expensive to leave around forever,
so they are swept on a schedule rather than in the request path.
"""

from datetime import datetime, timedelta

from flask import current_app

from common.database import db
from models.merchant_intro_video import MerchantIntroVideo


def run_purge_deleted_intro_videos(batch_size=100):
    """
    Hard-delete soft-deleted intro videos past the retention window, removing
    their S3 objects first.

    Returns a summary dict. Never raises: this runs in a scheduler thread, and
    one bad row must not kill the job.
    """
    retention_days = current_app.config.get('INTRO_VIDEO_PURGE_RETENTION_DAYS', 30)
    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    summary = {'examined': 0, 'rows_deleted': 0, 's3_failures': 0, 'errors': 0}

    rows = (
        MerchantIntroVideo.query
        .filter(
            MerchantIntroVideo.deleted_at.isnot(None),
            MerchantIntroVideo.deleted_at < cutoff,
        )
        .limit(batch_size)
        .all()
    )
    if not rows:
        return summary

    s3 = None
    try:
        from services.merchant_intro_video_s3_service import (
            get_merchant_intro_video_s3_service,
        )
        s3 = get_merchant_intro_video_s3_service()
    except Exception as e:
        # No storage service: still purge the rows we can, but keep the objects
        # so a later run with working config can find them via the row. Bail out
        # instead, so we never lose the only pointer to an S3 object.
        current_app.logger.warning(
            f"[INTRO_VIDEO_PURGE] Storage unavailable, skipping this run: {e}"
        )
        return summary

    for row in rows:
        summary['examined'] += 1
        try:
            if row.video_s3_key or row.thumbnail_s3_key:
                if not s3.delete_intro_video(row.video_s3_key, row.thumbnail_s3_key):
                    summary['s3_failures'] += 1
                    # Leave the row so the object can be retried next run.
                    continue
            db.session.delete(row)
            summary['rows_deleted'] += 1
        except Exception as e:
            summary['errors'] += 1
            current_app.logger.error(
                f"[INTRO_VIDEO_PURGE] Failed to purge intro video {row.id}: {e}",
                exc_info=True,
            )

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        summary['errors'] += 1
        current_app.logger.error(
            f"[INTRO_VIDEO_PURGE] Commit failed: {e}", exc_info=True
        )

    current_app.logger.info(f"[INTRO_VIDEO_PURGE] {summary}")
    return summary
