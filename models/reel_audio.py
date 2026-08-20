# models/reel_audio.py
"""Which song a reel uses, and where in the song it starts.

**This row exists even when the audio has been mixed into the video file.** That
is the whole point of it. Once a song is burned into an MP4 the file itself can no
longer tell you which track it was, where the clip started, or how the levels were
set — that information is gone unless it was written down here first.

Keeping it buys three things that are otherwise impossible after the fact:

* "Use this sound" — tap a song, see every reel using it, which is a plain
  `WHERE song_id = ...` and needs nothing from the video file.
* Re-rendering — change the song, move the start point, adjust the mix, and the
  reel can be rebuilt from the original video plus this row.
* Rights response — if a track has to be pulled, this is the only way to find
  every reel that used it.

One row per reel: a reel has at most one chosen song.
"""
from datetime import datetime, timezone

from common.database import db


class ReelAudio(db.Model):
    __tablename__ = "reel_audio"

    reel_audio_id = db.Column(db.Integer, primary_key=True)

    reel_id = db.Column(
        db.Integer,
        db.ForeignKey("reels.reel_id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    # Not a hard FK to songs: a track may be purged from the catalogue while reels
    # that used it still exist, and losing the id would destroy the audit trail
    # that is this table's reason for existing.
    song_id = db.Column(db.Integer, nullable=False, index=True)

    # The chosen clip, in milliseconds from the start of the track.
    start_ms = db.Column(db.Integer, nullable=False, default=0)
    end_ms = db.Column(db.Integer, nullable=True)

    # Mix levels, 0..1. The original audio is ducked rather than silenced so a
    # merchant describing the product stays audible under the music.
    music_volume = db.Column(db.Numeric(4, 3), nullable=False, default=1.000)
    original_volume = db.Column(db.Numeric(4, 3), nullable=False, default=0.150)

    # --- render state ---
    # Whether a mixed file has been produced, and which one. Null means playback
    # is expected to mix at the player instead.
    rendered_video_url = db.Column(db.String(512), nullable=True)
    rendered_at = db.Column(db.DateTime, nullable=True)
    # Set when a render is attempted and fails, so a broken reel is visible rather
    # than silently audio-less.
    render_error = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def duration_ms(self, song_duration_ms=None):
        """Length of the chosen clip, falling back to the rest of the track."""
        if self.end_ms is not None:
            return max(0, int(self.end_ms) - int(self.start_ms))
        if song_duration_ms:
            return max(0, int(song_duration_ms) - int(self.start_ms))
        return 0

    def serialize(self, song=None):
        out = {
            "reel_id": self.reel_id,
            "song_id": self.song_id,
            "start_ms": int(self.start_ms or 0),
            "end_ms": int(self.end_ms) if self.end_ms is not None else None,
            "music_volume": float(self.music_volume),
            "original_volume": float(self.original_volume),
            "rendered": self.rendered_video_url is not None,
        }
        if song is not None:
            out["song"] = song.serialize()
        return out

    def __repr__(self):
        return f"<ReelAudio reel={self.reel_id} song={self.song_id} @{self.start_ms}ms>"
