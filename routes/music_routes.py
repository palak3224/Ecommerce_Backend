# routes/music_routes.py
"""The music library, and attaching a song to a reel.

Two audiences with different rules:

* **Merchants** browse and attach. They never upload audio — that is the whole
  licensing argument, and it is enforced by there being no endpoint for it.
* **Admins** curate: ingest from a provider, upload a file, feature a track, or
  pull one.

The browse response deliberately omits `audio_url`. The full track is the licensed
asset; a page of fifty songs should not hand out fifty downloadable links. The
picker plays `preview_url`, and the full URL is fetched for the one song actually
chosen.
"""
from flask import Blueprint, current_app, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_

from auth.models.models import MerchantProfile
from common.database import db
from common.response import error_response, success_response
from models.reel import Reel
from models.reel_audio import ReelAudio
from models.song import Song

music_bp = Blueprint("music", __name__)

MAX_PAGE_SIZE = 50


def _visible_songs():
    """Base query for anything a merchant is allowed to see."""
    return Song.query.filter(Song.is_active.is_(True))


@music_bp.route("/api/music/songs", methods=["GET"])
@jwt_required()
def list_songs():
    """Browse and search the library.

    `category` maps to the curated buckets the picker shows as tabs. 'trending' is
    admin-ordered rather than purely organic, because a brand-new catalogue has no
    usage data and an empty trending tab is a bad first impression.
    """
    q = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "trending").strip().lower()
    page = max(1, request.args.get("page", default=1, type=int))
    per_page = min(request.args.get("per_page", default=20, type=int), MAX_PAGE_SIZE)

    query = _visible_songs()

    if q:
        like = f"%{q}%"
        query = query.filter(or_(Song.title.ilike(like),
                                 Song.artist.ilike(like),
                                 Song.tags.ilike(like)))

    if category == "trending":
        # Featured first in admin order, then whatever merchants actually use.
        query = query.order_by(
            Song.trending_rank.is_(None),      # False (featured) sorts first
            Song.trending_rank.asc(),
            Song.usage_count.desc(),
            Song.song_id.desc(),
        )
    elif category in ("new", "latest"):
        query = query.order_by(Song.created_at.desc())
    elif category == "popular":
        query = query.order_by(Song.usage_count.desc(), Song.song_id.desc())
    elif category != "all":
        query = query.filter(Song.tags.ilike(f"%{category}%")).order_by(
            Song.usage_count.desc()
        )

    paged = query.paginate(page=page, per_page=per_page, error_out=False)

    return success_response("Songs retrieved", {
        "songs": [s.serialize() for s in paged.items],
        "pagination": {
            "page": paged.page,
            "per_page": paged.per_page,
            "total": paged.total,
            "pages": paged.pages,
        },
    })


@music_bp.route("/api/music/songs/<int:song_id>", methods=["GET"])
@jwt_required()
def get_song(song_id):
    """One song, with the full audio URL and waveform — for the trim screen."""
    song = _visible_songs().filter(Song.song_id == song_id).first()
    if not song or not song.is_available():
        return error_response("Song not found or no longer available.", 404)
    return success_response("Song retrieved",
                            song.serialize(include_audio=True, include_peaks=True))


@music_bp.route("/api/music/categories", methods=["GET"])
@jwt_required()
def list_categories():
    """Tabs for the picker: the fixed buckets plus whatever tags exist."""
    rows = _visible_songs().with_entities(Song.tags).all()
    tags = set()
    for (raw,) in rows:
        for t in (raw or "").split(","):
            t = t.strip().lower()
            if t:
                tags.add(t)

    return success_response("Categories retrieved", {
        "categories": ["trending", "new", "popular"] + sorted(tags),
    })


# --------------------------------------------------------------------------- #
# attaching a song to a reel
# --------------------------------------------------------------------------- #

def _merchant_reel_or_error(reel_id):
    """The caller's own reel, or an error tuple. Merchants edit only their own."""
    merchant = MerchantProfile.get_by_user_id(get_jwt_identity())
    if not merchant:
        return None, error_response("Merchant profile not found.", 404)
    reel = Reel.query.filter_by(reel_id=reel_id, merchant_id=merchant.id).first()
    if not reel:
        return None, error_response("Reel not found.", 404)
    return reel, None


@music_bp.route("/api/reels/<int:reel_id>/audio", methods=["PUT"])
@jwt_required()
def set_reel_audio(reel_id):
    """Attach a song, or move the trim window on one already attached.

    Stores the choice as data. Whether the audio is later mixed into the file or
    played alongside it, this row is what records which track was used and where
    it started — information the video file itself cannot carry.
    """
    reel, err = _merchant_reel_or_error(reel_id)
    if err:
        return err

    data = request.get_json(silent=True) or {}
    song_id = data.get("song_id")
    if not song_id:
        return error_response("song_id is required.", 400)

    song = Song.query.get(song_id)
    if not song or not song.is_available():
        return error_response("Song not found or no longer available.", 404)

    try:
        start_ms = max(0, int(data.get("start_ms", 0)))
    except (TypeError, ValueError):
        return error_response("start_ms must be a whole number of milliseconds.", 400)

    end_ms = data.get("end_ms")
    if end_ms is not None:
        try:
            end_ms = int(end_ms)
        except (TypeError, ValueError):
            return error_response("end_ms must be a whole number of milliseconds.", 400)
        if end_ms <= start_ms:
            return error_response("end_ms must be after start_ms.", 400)

    if song.duration_ms and start_ms >= song.duration_ms:
        return error_response("The clip starts after the end of the track.", 400)

    def _volume(key, default):
        raw = data.get(key, default)
        try:
            v = float(raw)
        except (TypeError, ValueError):
            return None
        return min(max(v, 0.0), 1.0)

    music_volume = _volume("music_volume", 1.0)
    original_volume = _volume("original_volume", 0.15)
    if music_volume is None or original_volume is None:
        return error_response("Volumes must be numbers between 0 and 1.", 400)

    link = ReelAudio.query.filter_by(reel_id=reel_id).first()
    previous_song_id = link.song_id if link else None

    if link is None:
        link = ReelAudio(reel_id=reel_id)
        db.session.add(link)

    link.song_id = song.song_id
    link.start_ms = start_ms
    link.end_ms = end_ms
    link.music_volume = music_volume
    link.original_volume = original_volume
    # Any existing render is stale the moment the selection changes.
    link.rendered_video_url = None
    link.rendered_at = None
    link.render_error = None

    # Usage drives the 'popular' tab. Adjust both sides when a merchant swaps
    # tracks, so counts stay honest rather than only ever going up.
    if previous_song_id != song.song_id:
        song.usage_count = (song.usage_count or 0) + 1
        if previous_song_id:
            old = Song.query.get(previous_song_id)
            if old and old.usage_count:
                old.usage_count -= 1

    db.session.commit()
    return success_response("Audio attached to reel", link.serialize(song=song))


@music_bp.route("/api/reels/<int:reel_id>/audio", methods=["GET"])
@jwt_required()
def get_reel_audio(reel_id):
    reel, err = _merchant_reel_or_error(reel_id)
    if err:
        return err

    link = ReelAudio.query.filter_by(reel_id=reel_id).first()
    if not link:
        return success_response("No audio attached", None)

    return success_response("Reel audio retrieved",
                            link.serialize(song=Song.query.get(link.song_id)))


@music_bp.route("/api/reels/<int:reel_id>/audio", methods=["DELETE"])
@jwt_required()
def remove_reel_audio(reel_id):
    reel, err = _merchant_reel_or_error(reel_id)
    if err:
        return err

    link = ReelAudio.query.filter_by(reel_id=reel_id).first()
    if not link:
        return success_response("No audio attached", None)

    song = Song.query.get(link.song_id)
    if song and song.usage_count:
        song.usage_count -= 1

    db.session.delete(link)
    db.session.commit()
    return success_response("Audio removed from reel", None)


@music_bp.route("/api/music/songs/<int:song_id>/reels", methods=["GET"])
def reels_using_song(song_id):
    """"Use this sound" — every reel that chose this track.

    Works whether or not the audio was mixed into the video, because it reads the
    stored song_id rather than inspecting any file. This is the payoff for keeping
    reel_audio even in a merge-on-upload design.
    """
    page = max(1, request.args.get("page", default=1, type=int))
    per_page = min(request.args.get("per_page", default=20, type=int), MAX_PAGE_SIZE)

    song = Song.query.get(song_id)
    if not song:
        return error_response("Song not found.", 404)

    paged = (
        db.session.query(Reel)
        .join(ReelAudio, ReelAudio.reel_id == Reel.reel_id)
        .filter(ReelAudio.song_id == song_id)
        .order_by(Reel.reel_id.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return success_response("Reels retrieved", {
        "song": song.serialize(),
        "reels": [r.serialize() if hasattr(r, "serialize") else {"reel_id": r.reel_id}
                  for r in paged.items],
        "pagination": {"page": paged.page, "per_page": paged.per_page,
                       "total": paged.total, "pages": paged.pages},
    })


# --------------------------------------------------------------------------- #
# admin curation
# --------------------------------------------------------------------------- #
# Deliberately admin-only. There is no merchant-facing upload endpoint anywhere in
# this file, and that absence is the licensing control: a merchant who cannot
# upload audio cannot put an unlicensed track on the platform.

@music_bp.route("/api/superadmin/music/ingest", methods=["POST"])
@jwt_required()
def admin_ingest():
    """Pull a page of tracks from a provider into the catalogue."""
    from auth.models.models import User, UserRole
    from services.music.ingest_service import IngestError, ingest_from_provider

    user = User.query.get(get_jwt_identity())
    if not user or user.role != UserRole.SUPER_ADMIN:
        return error_response("Admin access required.", 403)

    data = request.get_json(silent=True) or {}
    provider = (data.get("provider") or "").strip().lower()
    if not provider:
        return error_response("provider is required.", 400)

    try:
        result = ingest_from_provider(
            provider,
            query=data.get("query"),
            limit=min(int(data.get("limit", 50)), 200),
            page=max(1, int(data.get("page", 1))),
        )
    except IngestError as e:
        return error_response(str(e), 400)

    return success_response("Ingest complete", result)


@music_bp.route("/api/superadmin/music/songs", methods=["POST"])
@jwt_required()
def admin_add_song():
    """Add one track by URL.

    This is the path for catalogues with no API — Pixabay, or a label delivering
    files. The admin supplies the audio URL and the rights metadata; the server
    downloads it once to measure duration and draw the waveform.
    """
    from auth.models.models import User, UserRole
    from services.music.ingest_service import IngestError, upsert_song

    user = User.query.get(get_jwt_identity())
    if not user or user.role != UserRole.SUPER_ADMIN:
        return error_response("Admin access required.", 403)

    data = request.get_json(silent=True) or {}
    if not data.get("audio_url") or not data.get("title"):
        return error_response("title and audio_url are required.", 400)

    track = dict(data)
    track.setdefault("provider_track_id", data["audio_url"][-100:])

    try:
        song, created = upsert_song("manual", track)
    except IngestError as e:
        return error_response(str(e), 400)

    return success_response(
        "Song added" if created else "Song updated",
        song.serialize(include_audio=True, include_peaks=True),
        201 if created else 200,
    )


@music_bp.route("/api/superadmin/music/songs/<int:song_id>", methods=["PATCH"])
@jwt_required()
def admin_update_song(song_id):
    """Feature, re-tag, or pull a track.

    `is_active=false` is the kill switch: the song leaves the picker immediately,
    while reels that already used it keep their reel_audio row so the link — and
    the record of what was used — survives.
    """
    from auth.models.models import User, UserRole

    user = User.query.get(get_jwt_identity())
    if not user or user.role != UserRole.SUPER_ADMIN:
        return error_response("Admin access required.", 403)

    song = Song.query.get(song_id)
    if not song:
        return error_response("Song not found.", 404)

    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        song.is_active = bool(data["is_active"])
    if "trending_rank" in data:
        rank = data["trending_rank"]
        song.trending_rank = None if rank is None else int(rank)
    if "tags" in data:
        song.tags = (data["tags"] or None) and str(data["tags"])[:500]
    if "language" in data:
        song.language = data["language"]
    if "title" in data:
        song.title = str(data["title"])[:255]
    if "artist" in data:
        song.artist = str(data["artist"])[:255]

    db.session.commit()
    return success_response("Song updated", song.serialize(include_audio=True))


@music_bp.route("/api/superadmin/music/songs/upload", methods=["POST"])
@jwt_required()
def admin_upload_song():
    """Add a track by uploading the audio file itself.

    The main path for a catalogue with no API. Downloading from Pixabay leaves a
    file on a laptop, not a URL, so asking an admin for a link would mean hosting
    it somewhere else first — this takes what they actually have.

    Multipart: `file` plus the same metadata fields the JSON endpoint accepts.
    Length and waveform are measured from the audio, never taken from the form.
    """
    from auth.models.models import User, UserRole
    from services.music.ingest_service import IngestError, upsert_song
    from services.music.song_upload_service import (
        SongUploadError, upload_artwork_file, upload_song_file,
    )

    user = User.query.get(get_jwt_identity())
    if not user or user.role != UserRole.SUPER_ADMIN:
        return error_response("Admin access required.", 403)

    if "file" not in request.files:
        return error_response("No audio file was uploaded.", 400)

    title = (request.form.get("title") or "").strip()
    if not title:
        return error_response("Title is required.", 400)

    try:
        stored = upload_song_file(request.files["file"])
        # Optional cover image, uploaded the same way. Falls back to a pasted URL
        # for catalogues that already host their artwork.
        artwork_url = (request.form.get("artwork_url") or "").strip() or None
        if request.files.get("artwork"):
            artwork_url = upload_artwork_file(request.files["artwork"])
    except SongUploadError as e:
        return error_response(str(e), 400)
    except Exception as e:
        current_app.logger.error("Song upload failed: %s", e, exc_info=True)
        return error_response("Could not process the audio file.", 500)

    track = {
        "provider_track_id": stored["s3_key"],
        "title": title,
        "artist": (request.form.get("artist") or "").strip() or None,
        "artwork_url": artwork_url,
        "audio_url": stored["audio_url"],
        "preview_url": stored["audio_url"],
        "duration_ms": stored["duration_ms"],
        "tags": (request.form.get("tags") or "").strip() or None,
        "language": (request.form.get("language") or "").strip() or None,
        "licence_name": (request.form.get("licence_name") or "").strip() or None,
        "licence_url": (request.form.get("licence_url") or "").strip() or None,
        "attribution_text": (request.form.get("attribution_text") or "").strip() or None,
        "attribution_required": bool((request.form.get("attribution_text") or "").strip()),
    }

    try:
        # analyse=False: the file has already been measured on the way in, and
        # re-downloading it from CloudFront to do it again would be wasteful.
        song, created = upsert_song("manual", track, analyse=False)
    except IngestError as e:
        return error_response(str(e), 400)

    if stored["waveform_peaks"]:
        import json as _json
        song.waveform_peaks = _json.dumps(stored["waveform_peaks"])
        db.session.commit()

    return success_response(
        "Song uploaded",
        song.serialize(include_audio=True, include_peaks=True),
        201 if created else 200,
    )
