"""Reel music: the catalogue, the trim selection, and the mux.

The load-bearing assertion here is `test_reel_audio_survives_a_merged_render`.
Once a song is mixed into an MP4 the file cannot say which track it was or where
the clip started. The reel_audio row is the only record, and "use this sound",
re-rendering and any rights response all depend on it existing.
"""
import os
import shutil
import subprocess
import tempfile

import pytest

from app import create_app
from common.database import db


HAS_FFMPEG = shutil.which("ffmpeg") is not None


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


_SEQ = [0]


def _mk_song(title="Track", provider="manual", tags="pop,trending",
             duration_ms=180000, rank=None, active=True):
    from models.song import Song
    _SEQ[0] += 1
    s = Song(provider=provider, provider_track_id=f"t{_SEQ[0]}",
             title=title, artist="Artist", duration_ms=duration_ms,
             audio_url=f"https://cdn.example/{_SEQ[0]}.mp3",
             preview_url=f"https://cdn.example/{_SEQ[0]}-preview.mp3",
             tags=tags, trending_rank=rank, is_active=active)
    db.session.add(s); db.session.commit()
    return s


# --------------------------------------------------------------------------- #
# the catalogue
# --------------------------------------------------------------------------- #

def test_browse_withholds_the_full_audio_url(app):
    """A page of songs must not hand out a downloadable link for each one."""
    with app.app_context():
        song = _mk_song()
        listed = song.serialize()
        assert "preview_url" in listed
        assert "audio_url" not in listed, "full track leaked into a browse response"

        chosen = song.serialize(include_audio=True, include_peaks=True)
        assert chosen["audio_url"].endswith(".mp3")


def test_an_inactive_song_is_not_available(app):
    """The kill switch — one flag pulls a track from the picker."""
    with app.app_context():
        song = _mk_song(active=False)
        assert song.is_available() is False


def test_an_expired_licence_makes_a_song_unavailable(app):
    from datetime import datetime, timedelta, timezone
    with app.app_context():
        song = _mk_song()
        song.licence_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.session.commit()
        assert song.is_expired() is True
        assert song.is_available() is False


def test_ingest_is_idempotent_on_provider_and_track_id(app):
    """Re-running a fetch updates rows rather than duplicating the catalogue."""
    from models.song import Song
    from services.music.ingest_service import upsert_song

    with app.app_context():
        track = {"provider_track_id": "abc123", "title": "Song A",
                 "audio_url": "https://cdn.example/a.mp3", "duration_ms": 120000}

        first, created_1 = upsert_song("manual", track, analyse=False)
        track["title"] = "Song A (remastered)"
        second, created_2 = upsert_song("manual", track, analyse=False)

        assert created_1 is True and created_2 is False
        assert first.song_id == second.song_id
        assert Song.query.count() == 1
        assert second.title == "Song A (remastered)"


def test_ingest_rejects_a_track_with_no_audio(app):
    from services.music.ingest_service import IngestError, upsert_song

    with app.app_context():
        with pytest.raises(IngestError, match="audio_url"):
            upsert_song("manual", {"provider_track_id": "x", "title": "No audio"},
                        analyse=False)


def test_unknown_provider_is_rejected_by_name(app):
    from services.music.providers import ProviderError, get_provider

    with app.app_context():
        with pytest.raises(ProviderError, match="Unknown music provider"):
            get_provider("spotify")


# --------------------------------------------------------------------------- #
# the trim selection
# --------------------------------------------------------------------------- #

def test_reel_audio_records_the_clip_window(app):
    from models.reel_audio import ReelAudio

    with app.app_context():
        song = _mk_song(duration_ms=180000)
        link = ReelAudio(reel_id=1, song_id=song.song_id,
                         start_ms=30000, end_ms=45000)
        db.session.add(link); db.session.commit()

        assert link.duration_ms() == 15000
        # With no end, the clip runs to the end of the track.
        link.end_ms = None
        assert link.duration_ms(song_duration_ms=song.duration_ms) == 150000


def test_use_this_sound_needs_only_the_stored_song_id(app):
    """The whole reason reel_audio exists in a merge-on-upload design.

    Finding every reel that used a track is a query over stored ids — it never
    inspects a video file, so it works identically whether the audio was mixed in
    or played alongside.
    """
    from models.reel_audio import ReelAudio

    with app.app_context():
        song = _mk_song()
        other = _mk_song(title="Other")
        for reel_id in (10, 11, 12):
            db.session.add(ReelAudio(reel_id=reel_id, song_id=song.song_id))
        db.session.add(ReelAudio(reel_id=13, song_id=other.song_id))
        db.session.commit()

        using = ReelAudio.query.filter_by(song_id=song.song_id).all()
        assert sorted(r.reel_id for r in using) == [10, 11, 12]


def test_reel_audio_survives_a_merged_render(app):
    """Metadata must outlive the mix.

    After a render the MP4 carries the music but no idea which track it was. If
    this row were dropped once the file existed, "use this sound", re-rendering
    and any takedown response would all become impossible.
    """
    from datetime import datetime, timezone
    from models.reel_audio import ReelAudio

    with app.app_context():
        song = _mk_song()
        link = ReelAudio(reel_id=99, song_id=song.song_id, start_ms=12000)
        db.session.add(link); db.session.commit()

        link.rendered_video_url = "https://cdn.example/reel-99-mixed.mp4"
        link.rendered_at = datetime.now(timezone.utc)
        db.session.commit()
        db.session.expire_all()

        after = ReelAudio.query.filter_by(reel_id=99).first()
        assert after.song_id == song.song_id
        assert after.start_ms == 12000
        assert after.rendered_video_url is not None


# --------------------------------------------------------------------------- #
# ffmpeg
# --------------------------------------------------------------------------- #

def test_mux_command_copies_the_video_stream(app):
    """-c:v copy is what makes a re-mix cheap enough to treat as a cache."""
    from services.music.audio_mux_service import build_mux_command

    with app.app_context():
        cmd = build_mux_command("in.mp4", "song.mp3", "out.mp4",
                                start_ms=30000, duration_ms=15000,
                                music_volume=0.8, original_volume=0.2)
        joined = " ".join(cmd)

        assert "-c:v copy" in joined, "video would be re-encoded"
        assert "-ss 30.000" in joined
        assert "-t 15.000" in joined
        assert "volume=0.200" in joined and "volume=0.800" in joined
        assert "amix=inputs=2" in joined


def test_mux_can_drop_the_original_audio(app):
    from services.music.audio_mux_service import build_mux_command

    with app.app_context():
        cmd = " ".join(build_mux_command("in.mp4", "s.mp3", "out.mp4",
                                         keep_original_audio=False))
        assert "amix" not in cmd
        assert "-c:v copy" in cmd


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_mux_actually_produces_a_playable_file(app):
    """End to end against real ffmpeg, not just the argv."""
    from services.music.audio_mux_service import mux

    with app.app_context():
        tmp = tempfile.mkdtemp()
        try:
            video = os.path.join(tmp, "reel.mp4")
            audio = os.path.join(tmp, "song.mp3")
            out = os.path.join(tmp, "out.mp4")

            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                            "-i", "testsrc=size=320x568:rate=30:duration=5",
                            "-f", "lavfi", "-i", "sine=frequency=200:duration=5",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-shortest", video, "-y"], check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                            "-i", "sine=frequency=800:duration=30",
                            "-c:a", "libmp3lame", audio, "-y"], check=True)

            mux(video, audio, out, start_ms=10000, duration_ms=5000)

            assert os.path.getsize(out) > 0
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "stream=codec_type", "-of", "csv=p=0", out],
                capture_output=True, text=True)
            assert "video" in probe.stdout and "audio" in probe.stdout
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_waveform_peaks_are_small_and_normalised(app):
    """The trim bar needs a shape, not a signal — and it must ship cheaply."""
    from services.music.waveform_service import generate_peaks

    with app.app_context():
        tmp = tempfile.mkdtemp()
        try:
            audio = os.path.join(tmp, "s.mp3")
            # Amplitude ramp, so the envelope is genuinely uneven.
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                            "-i", "sine=frequency=440:duration=20",
                            "-filter:a", "volume='min(1,t/20)':eval=frame",
                            "-c:a", "libmp3lame", audio, "-y"], check=True)

            peaks = generate_peaks(audio, buckets=120)

            assert len(peaks) == 120
            assert all(0.0 <= p <= 1.0 for p in peaks)
            assert max(peaks) == pytest.approx(1.0, abs=0.01), "not normalised"
            # A ramp must not come out flat, or the trim bar shows nothing useful.
            assert peaks[-1] > peaks[0]
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def test_missing_audio_file_yields_no_peaks_rather_than_raising(app):
    """A missing waveform degrades the trim UI; it must not fail an ingest."""
    from services.music.waveform_service import generate_peaks

    with app.app_context():
        assert generate_peaks("/nonexistent/file.mp3") == []


# --------------------------------------------------------------------------- #
# duration probing — the production failure
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_duration_is_read_without_ffprobe(app):
    """The server has ffmpeg but not necessarily ffprobe.

    app.py checks for ffmpeg at boot and says nothing about ffprobe — they are
    separate binaries. Reading duration through ffprobe alone made every upload
    fail with "this file does not look like playable audio" on a box where the
    audio was fine.
    """
    from unittest.mock import patch
    from services.music import waveform_service
    from services.music.waveform_service import probe_duration_ms

    with app.app_context():
        tmp = tempfile.mkdtemp()
        try:
            audio = os.path.join(tmp, "t.mp3")
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                            "-i", "sine=frequency=440:duration=7.5",
                            "-c:a", "libmp3lame", audio, "-y"], check=True)

            assert probe_duration_ms(audio) == pytest.approx(7500, abs=200)

            real_which = shutil.which
            with patch.object(waveform_service.shutil, "which",
                              lambda n: None if n == "ffprobe" else real_which(n)):
                without = probe_duration_ms(audio)
            assert without == pytest.approx(7500, abs=200), \
                "duration unreadable without ffprobe"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def test_missing_tooling_is_reported_as_such(app):
    """An ops problem must not be reported as a bad file.

    Telling an admin their mp3 is corrupt when the truth is ffmpeg is missing
    sends them off re-exporting a file that was always fine.
    """
    from unittest.mock import patch
    from services.music import waveform_service

    with app.app_context():
        # Both routes blocked: PATH lookup and the known-directory fallback. Only
        # blinding shutil.which is no longer enough, because find_binary goes on
        # to check /usr/bin and friends — which is the whole point of it.
        with patch.object(waveform_service, "find_binary", lambda n: None):
            assert waveform_service.audio_tooling_available() is False


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_ffmpeg_is_found_when_path_does_not_contain_it(app):
    """The production failure: installed at /usr/bin, invisible to PATH.

    The systemd unit sets PATH to the virtualenv's bin directory and nothing
    else, so shutil.which() finds neither ffmpeg nor ffprobe even though both are
    present. app.py already checks known locations for exactly this reason; the
    music services did not, and rejected valid audio as unplayable.
    """
    from unittest.mock import patch
    from services.music import waveform_service
    from services.music.waveform_service import find_binary, probe_duration_ms

    with app.app_context():
        tmp = tempfile.mkdtemp()
        try:
            audio = os.path.join(tmp, "t.mp3")
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                            "-i", "sine=frequency=440:duration=4",
                            "-c:a", "libmp3lame", audio, "-y"], check=True)

            # shutil.which blind, exactly as it is under systemd.
            with patch.object(waveform_service.shutil, "which", lambda n: None):
                located = find_binary("ffmpeg")
                # Only meaningful where ffmpeg sits in one of the known dirs.
                if located is None:
                    pytest.skip("ffmpeg is not in a conventional bin directory here")

                assert waveform_service.audio_tooling_available() is True
                assert probe_duration_ms(audio) == pytest.approx(4000, abs=200)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
