# models/merchant_intro_video.py
from datetime import datetime

from common.database import db, BaseModel


# Upload lifecycle. `processing` exists so a future presigned-upload flow can
# create the row before the bytes land without changing the schema.
STATUS_PROCESSING = 'processing'
STATUS_READY = 'ready'
STATUS_FAILED = 'failed'

MODERATION_PENDING = 'pending'
MODERATION_APPROVED = 'approved'
MODERATION_REJECTED = 'rejected'


class MerchantIntroVideo(BaseModel):
    """
    A merchant's self-introduction video. One active row per merchant.

    A dedicated table rather than columns on merchant_profiles: replace and
    delete are first-class operations here, and a row gives us an upload
    lifecycle, a moderation trail, soft delete, and a record of the S3 objects
    an orphan-sweep needs to clean up.
    """
    __tablename__ = 'merchant_intro_videos'
    __table_args__ = (
        # MySQL has no partial unique index, so "one active video per merchant"
        # cannot be a constraint alongside soft-deleted history rows; it is
        # enforced in the controller under SELECT ... FOR UPDATE. This index
        # serves the lookup that guard performs.
        db.Index('idx_merchant_intro_videos_merchant_active', 'merchant_id', 'deleted_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(
        db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False, index=True
    )

    title = db.Column(db.String(120), nullable=True)
    caption = db.Column(db.String(500), nullable=True)

    video_url = db.Column(db.String(512), nullable=True)  # null while processing
    video_s3_key = db.Column(db.String(512), nullable=True)
    thumbnail_url = db.Column(db.String(512), nullable=True)  # null when ffmpeg is unavailable
    thumbnail_s3_key = db.Column(db.String(512), nullable=True)

    duration_seconds = db.Column(db.Integer, nullable=True)  # unverified hint unless ffprobe ran
    duration_verified = db.Column(db.Boolean, nullable=False, default=False)
    file_size_bytes = db.Column(db.BigInteger, nullable=True)
    video_format = db.Column(db.String(10), nullable=True)  # mp4 | mov
    mime_type = db.Column(db.String(60), nullable=True)
    resolution = db.Column(db.String(20), nullable=True)  # e.g. "1080x1920"

    status = db.Column(db.String(20), nullable=False, default=STATUS_PROCESSING, index=True)
    failure_reason = db.Column(db.String(255), nullable=True)

    moderation_status = db.Column(
        db.String(20), nullable=False, default=MODERATION_APPROVED, index=True
    )
    moderation_notes = db.Column(db.String(500), nullable=True)
    moderated_at = db.Column(db.DateTime, nullable=True)
    moderated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)  # merchant's own show/hide
    deleted_at = db.Column(db.DateTime, nullable=True, index=True)

    merchant = db.relationship('MerchantProfile', backref=db.backref('intro_videos', lazy='dynamic'))

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    @classmethod
    def get_active_for_merchant(cls, merchant_id):
        """The merchant's current (non-deleted) intro video, whatever its state."""
        return cls.query.filter(
            cls.merchant_id == merchant_id,
            cls.deleted_at.is_(None)
        ).order_by(cls.created_at.desc()).first()

    @classmethod
    def lock_active_for_merchant(cls, merchant_id):
        """
        Same as get_active_for_merchant but takes a row lock, so two concurrent
        uploads cannot both pass the "does one already exist?" check.

        SQLite (used by the test config) ignores FOR UPDATE, which is fine —
        the tests are single-threaded.
        """
        return cls.query.filter(
            cls.merchant_id == merchant_id,
            cls.deleted_at.is_(None)
        ).order_by(cls.created_at.desc()).with_for_update().first()

    @classmethod
    def count_uploads_since(cls, merchant_id, since):
        """Upload attempts (including deleted ones) since `since` — the daily cap."""
        return cls.query.filter(
            cls.merchant_id == merchant_id,
            cls.created_at >= since
        ).count()

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    def is_publicly_visible(self):
        """
        Whether this row itself may be shown publicly. The merchant must also
        pass MerchantProfile.is_public_media_visible() — checked by the caller.
        """
        return (
            self.deleted_at is None
            and bool(self.is_active)
            and self.status == STATUS_READY
            and self.moderation_status == MODERATION_APPROVED
        )

    def soft_delete(self):
        self.deleted_at = datetime.utcnow()
        self.is_active = False

    def serialize(self, owner_view=False):
        """
        Public shape by default. `owner_view` adds the lifecycle and moderation
        fields — those must never leak to shoppers.
        """
        data = {
            "id": self.id,
            "title": self.title,
            "caption": self.caption,
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "duration_seconds": self.duration_seconds,
            "resolution": self.resolution,
        }
        if owner_view:
            data.update({
                "file_size_bytes": self.file_size_bytes,
                "video_format": self.video_format,
                "mime_type": self.mime_type,
                "duration_verified": bool(self.duration_verified),
                "status": self.status,
                "failure_reason": self.failure_reason,
                "moderation_status": self.moderation_status,
                "moderation_notes": self.moderation_notes,
                "is_active": bool(self.is_active),
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            })
        return data
