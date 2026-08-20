# services/music/audio_mux_service.py
"""Mix a chosen song into a reel's video file.

The important flag here is `-c:v copy`: the video stream is copied through
untouched and only the audio is encoded. A ten second reel muxes in about 0.2
seconds, and the picture is bit-identical to what the merchant uploaded — no
generation loss, no re-encode queue.

That cost matters for a decision this design makes elsewhere: because muxing is
cheap, changing a song is cheap too, which is why `reel_audio` can stay the source
of truth and the rendered file can be treated as a cache.

The original audio is ducked rather than dropped, so a merchant talking over their
own video is still audible under the music.
"""
import os
import shutil
import subprocess
import tempfile

from flask import current_app


class AudioMuxError(Exception):
    """The mix could not be produced. The message is for logs, not merchants."""


def _ffmpeg_path():
    return shutil.which("ffmpeg") or "ffmpeg"


def build_mux_command(video_path, audio_path, out_path, *, start_ms=0,
                      duration_ms=None, music_volume=1.0, original_volume=0.15,
                      keep_original_audio=True):
    """The exact ffmpeg argv. Split out so it can be asserted on in tests."""
    start_s = max(0, int(start_ms)) / 1000.0

    cmd = [_ffmpeg_path(), "-v", "error", "-i", str(video_path)]

    # -ss before -i seeks the input, which is far faster than decoding to the
    # start point and discarding it.
    cmd += ["-ss", f"{start_s:.3f}"]
    if duration_ms:
        cmd += ["-t", f"{max(0, int(duration_ms)) / 1000.0:.3f}"]
    cmd += ["-i", str(audio_path)]

    if keep_original_audio:
        filt = (
            f"[0:a]volume={float(original_volume):.3f}[orig];"
            f"[1:a]volume={float(music_volume):.3f}[music];"
            f"[orig][music]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        cmd += ["-filter_complex", filt, "-map", "0:v", "-map", "[aout]"]
    else:
        cmd += ["-filter_complex", f"[1:a]volume={float(music_volume):.3f}[aout]",
                "-map", "0:v", "-map", "[aout]"]

    cmd += [
        "-c:v", "copy",          # the whole reason this is fast
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",   # so it starts playing before it fully downloads
        "-y", str(out_path),
    ]
    return cmd


def mux(video_path, audio_path, out_path, *, start_ms=0, duration_ms=None,
        music_volume=1.0, original_volume=0.15, keep_original_audio=True,
        timeout=300):
    """Mix and write to `out_path`. Raises AudioMuxError on failure."""
    cmd = build_mux_command(
        video_path, audio_path, out_path,
        start_ms=start_ms, duration_ms=duration_ms,
        music_volume=music_volume, original_volume=original_volume,
        keep_original_audio=keep_original_audio,
    )
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise AudioMuxError(f"ffmpeg timed out after {timeout}s")
    except (FileNotFoundError, OSError) as e:
        raise AudioMuxError(f"ffmpeg not available: {e}")

    if proc.returncode != 0:
        raise AudioMuxError(f"ffmpeg failed: {proc.stderr.decode()[:500]}")

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise AudioMuxError("ffmpeg reported success but produced no output")

    return out_path


def mux_to_tempfile(video_path, audio_path, **kwargs):
    """Convenience for callers that will upload the result and discard it."""
    fd, out_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        return mux(video_path, audio_path, out_path, **kwargs)
    except Exception:
        try:
            os.unlink(out_path)
        except OSError:
            pass
        raise


def has_ffmpeg():
    return shutil.which("ffmpeg") is not None
