# services/music/ingest_service.py
"""Bring tracks into the catalogue.

Ingest is **idempotent on (provider, provider_track_id)**. Re-running a fetch
updates the rows it already created rather than duplicating them, so a scheduled
refresh or a re-run after a partial failure is safe. That pair is a unique
constraint on the table, so the guarantee is enforced by the database rather than
by this code remembering to check.

Waveforms are generated here rather than lazily on first view, because the trim UI
needs one the instant a merchant taps a song, and generating it then would put an
ffmpeg run on the critical path of a tap.
"""
import os
import tempfile

import requests
from flask import current_app

from common.database import db
from models.song import Song
from services.music.providers import ProviderError, get_provider
from services.music.waveform_service import generate_peaks, probe_duration_ms

import json


MAX_AUDIO_BYTES = 25 * 1024 * 1024   # 25MB — a long track at a sane bitrate


class IngestError(Exception):
    """The track could not be taken in. Message is admin-facing."""


def _download_to_temp(url, timeout=60):
    """Fetch audio to a temp file so ffmpeg can read it.

    Streamed with a size cap: an ingest URL is supplied by an admin, but a typo
    pointing at something enormous should fail fast rather than fill the disk.
    """
    fd, path = tempfile.mkstemp(suffix=".audio")
    os.close(fd)
    try:
        with requests.get(url, stream=True, timeout=timeout) as resp:
            if resp.status_code != 200:
                raise IngestError(f"Could not download audio ({resp.status_code}).")
            written = 0
            with open(path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    written += len(chunk)
                    if written > MAX_AUDIO_BYTES:
                        raise IngestError("Audio file exceeds the size limit.")
                    fh.write(chunk)
        return path
    except IngestError:
        _unlink(path)
        raise
    except requests.RequestException as e:
        _unlink(path)
        raise IngestError(f"Could not download audio: {e}")


def _unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def upsert_song(provider_name, track, *, analyse=True):
    """Create or update one song. Returns (song, created)."""
    required = ("provider_track_id", "title", "audio_url")
    missing = [k for k in required if not track.get(k)]
    if missing:
        raise IngestError(f"Track is missing {', '.join(missing)}.")

    song = Song.query.filter_by(
        provider=provider_name,
        provider_track_id=str(track["provider_track_id"]),
    ).first()
    created = song is None
    if created:
        song = Song(provider=provider_name,
                    provider_track_id=str(track["provider_track_id"]))

    song.title = track["title"][:255]
    song.artist = (track.get("artist") or None) and track["artist"][:255]
    song.artwork_url = track.get("artwork_url")
    song.audio_url = track["audio_url"]
    song.preview_url = track.get("preview_url") or track["audio_url"]
    song.duration_ms = int(track.get("duration_ms") or 0)
    song.tags = (track.get("tags") or None) and track["tags"][:500]
    song.language = track.get("language")
    song.licence_name = track.get("licence_name")
    song.licence_url = track.get("licence_url")
    song.attribution_required = bool(track.get("attribution_required", False))
    song.attribution_text = (track.get("attribution_text") or None)
    if track.get("trending_rank") is not None:
        song.trending_rank = int(track["trending_rank"])

    # Analysis needs the actual bytes. Skipped when the caller already has the
    # numbers, or in tests where downloading is neither possible nor the point.
    if analyse and (not song.waveform_peaks or not song.duration_ms):
        tmp = None
        try:
            tmp = _download_to_temp(song.audio_url)
            peaks = generate_peaks(tmp)
            if peaks:
                song.waveform_peaks = json.dumps(peaks)
            if not song.duration_ms:
                song.duration_ms = probe_duration_ms(tmp)
        except IngestError as e:
            # A track without a waveform is still usable — the trim bar just has
            # no picture. Losing the whole ingest over it would be worse.
            _log("warning", "ingest: analysis skipped for %s: %s", song.title, e)
        finally:
            if tmp:
                _unlink(tmp)

    if created:
        db.session.add(song)
    db.session.commit()
    return song, created


def ingest_from_provider(provider_name, *, query=None, limit=50, page=1, analyse=True):
    """Pull a page from a catalogue and upsert it. Returns a summary."""
    try:
        provider = get_provider(provider_name)
        tracks = provider.fetch(query=query, limit=limit, page=page)
    except ProviderError as e:
        raise IngestError(str(e))

    created = updated = failed = 0
    errors = []
    for track in tracks:
        try:
            _, was_created = upsert_song(provider_name, track, analyse=analyse)
            created += 1 if was_created else 0
            updated += 0 if was_created else 1
        except Exception as e:
            # One bad track must not abandon the rest of the page.
            db.session.rollback()
            failed += 1
            errors.append(f"{track.get('title', '?')}: {e}")

    _log("info", "ingest %s: %s created, %s updated, %s failed",
         provider_name, created, updated, failed)

    return {
        "provider": provider_name,
        "created": created,
        "updated": updated,
        "failed": failed,
        "errors": errors[:10],
    }


def _log(level, msg, *args):
    try:
        getattr(current_app.logger, level)(msg, *args)
    except RuntimeError:
        pass
