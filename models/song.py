# models/song.py
"""The music library merchants pick from when making a reel.

Songs are **curated, never merchant-uploaded**. A merchant uploading their own
audio file is how a marketplace ends up serving copyrighted music it has no right
to, and takedowns land on the platform, not the uploader.

`provider` + `provider_track_id` is the identity of a track *at its source*, and
they are unique together so re-running an ingest updates rows instead of
duplicating them. That pair is also what makes the catalogue swappable: Pixabay
today, a label deal later, without touching the reel or playback code.

Licence fields are stored even when nothing currently checks them. The moment a
catalogue has an expiry or a territory restriction, `is_active` and
`allowed_territories` are the switches that already exist — retrofitting them
after a rights holder complains is not a position to be in.
"""
from datetime import datetime, timezone
import json

from common.database import db


class Song(db.Model):
    __tablename__ = "songs"

    song_id = db.Column(db.Integer, primary_key=True)

    # --- identity at the source ---
    provider = db.Column(db.String(40), nullable=False, index=True)   # pixabay | jamendo | manual | ...
    provider_track_id = db.Column(db.String(120), nullable=True, index=True)

    # --- what the merchant sees ---
    title = db.Column(db.String(255), nullable=False)
    artist = db.Column(db.String(255), nullable=True)
    artwork_url = db.Column(db.String(512), nullable=True)
    duration_ms = db.Column(db.Integer, nullable=False, default=0)

    # --- audio ---
    # Full track, used when a reel is actually rendered.
    audio_url = db.Column(db.String(512), nullable=False)
    audio_s3_key = db.Column(db.String(512), nullable=True)
    # Short, low-bitrate clip for browsing. Scrolling a library of 500 songs must
    # not stream 500 full tracks.
    preview_url = db.Column(db.String(512), nullable=True)

    # --- trim UI ---
    # JSON array of normalised 0..1 peaks, precomputed at ingest. Computing this on
    # the phone is slow and gives a different picture on every device.
    waveform_peaks = db.Column(db.Text, nullable=True)

    # --- discovery ---
    # Comma-separated, lowercase. A join table would be tidier but this is read far
    # more than it is written and the tag vocabulary is small and admin-controlled.
    tags = db.Column(db.String(500), nullable=True, index=True)
    language = db.Column(db.String(40), nullable=True, index=True)
    # Admin-curated ordering. NULL means "not featured"; lower sorts first.
    trending_rank = db.Column(db.Integer, nullable=True, index=True)
    # Organic signal, incremented as reels adopt the track.
    usage_count = db.Column(db.Integer, nullable=False, default=0, index=True)

    # --- rights ---
    licence_name = db.Column(db.String(120), nullable=True)
    licence_url = db.Column(db.String(512), nullable=True)
    attribution_required = db.Column(db.Boolean, nullable=False, default=False)
    attribution_text = db.Column(db.String(500), nullable=True)
    licence_expires_at = db.Column(db.DateTime, nullable=True)
    # NULL means "everywhere". Otherwise a comma-separated ISO country list.
    allowed_territories = db.Column(db.String(255), nullable=True)

    # The kill switch. Flipping this hides the track from the picker immediately;
    # reels already using it keep their stored song_id so the link survives.
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint("provider", "provider_track_id", name="uq_song_provider_track"),
    )

    def tag_list(self):
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]

    def peaks(self):
        if not self.waveform_peaks:
            return []
        try:
            return json.loads(self.waveform_peaks)
        except (TypeError, ValueError):
            return []

    def is_expired(self, now=None):
        if self.licence_expires_at is None:
            return False
        now = now or datetime.now(timezone.utc)
        expires = self.licence_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now >= expires

    def is_available(self, now=None):
        """Pickable right now — active and not past its licence."""
        return bool(self.is_active) and not self.is_expired(now)

    def serialize(self, include_audio=False, include_peaks=False):
        """Library listing shape.

        `audio_url` is withheld by default: the full track is the licensed asset,
        and a browse response for 50 songs should not hand out 50 downloadable
        links. The picker uses `preview_url`; the full URL is fetched for the one
        song actually chosen.
        """
        out = {
            "song_id": self.song_id,
            "title": self.title,
            "artist": self.artist,
            "artwork_url": self.artwork_url,
            "duration_ms": int(self.duration_ms or 0),
            "preview_url": self.preview_url,
            "tags": self.tag_list(),
            "language": self.language,
            "usage_count": int(self.usage_count or 0),
            "attribution_required": bool(self.attribution_required),
            "attribution_text": self.attribution_text,
            "provider": self.provider,
        }
        if include_peaks:
            out["waveform_peaks"] = self.peaks()
        if include_audio:
            out["audio_url"] = self.audio_url
        return out

    def __repr__(self):
        return f"<Song {self.song_id} {self.title!r} by {self.artist!r} ({self.provider})>"
