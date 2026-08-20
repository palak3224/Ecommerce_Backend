# services/music/waveform_service.py
"""Turn an audio file into a small array of peaks for the trim UI.

Done once at ingest, not on the phone. Computing a waveform client-side is slow on
cheap Android hardware and, worse, gives a slightly different picture on every
device — the same song would look different to two merchants.

The output is deliberately tiny: 120 buckets of 3 decimal places is about 600
bytes, which is cheaper to ship than one extra thumbnail.
"""
import json
import shutil
import struct
import subprocess

from flask import current_app


DEFAULT_BUCKETS = 120
# Decode at a reduced rate to keep the Python-side loop small, but NOT so low that
# the content disappears. Resampling to a few hundred Hz looks tempting — it is a
# tenth of the samples — but it puts anything above that Nyquist through the
# resampler's low-pass and deletes it: a 440Hz tone sampled at 400Hz reads as
# silence, and the waveform comes out flat zero. 8kHz keeps everything up to 4kHz,
# which is the whole musically-relevant envelope, at ~1.4M samples for a 3 minute
# track.
ENVELOPE_HZ = 8000


def _ffmpeg_path():
    return shutil.which("ffmpeg") or "ffmpeg"


def generate_peaks(audio_path, buckets=DEFAULT_BUCKETS, timeout=120):
    """Return a list of `buckets` floats in 0..1, or [] if it cannot be produced.

    Never raises. A missing waveform degrades the trim UI to a plain scrub bar,
    which is worth far less than failing an ingest over.
    """
    cmd = [
        _ffmpeg_path(), "-v", "error",
        "-i", str(audio_path),
        "-ac", "1",                          # mono; stereo doubles work for nothing
        "-ar", str(ENVELOPE_HZ),
        "-map", "0:a",
        "-c:a", "pcm_s16le",
        "-f", "data", "-",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        _log("warning", "waveform: ffmpeg unavailable or timed out: %s", e)
        return []

    if proc.returncode != 0:
        _log("warning", "waveform: ffmpeg failed: %s", proc.stderr.decode()[:300])
        return []

    raw = proc.stdout
    count = len(raw) // 2
    if count == 0:
        return []

    samples = struct.unpack(f"<{count}h", raw[: count * 2])
    step = max(1, count // buckets)

    peaks = []
    for i in range(0, count, step):
        window = samples[i : i + step]
        if not window:
            continue
        peaks.append(round(max(abs(s) for s in window) / 32768.0, 3))
        if len(peaks) == buckets:
            break

    # Normalise to the loudest point so a quiet track still fills the bar. Without
    # this a soft acoustic song renders as a nearly flat line and cannot be trimmed
    # by eye.
    loudest = max(peaks) if peaks else 0
    if loudest > 0:
        peaks = [round(p / loudest, 3) for p in peaks]

    return peaks


def peaks_json(audio_path, buckets=DEFAULT_BUCKETS):
    return json.dumps(generate_peaks(audio_path, buckets=buckets))


def probe_duration_ms(audio_path, timeout=30):
    """Track length in milliseconds, or 0 if it cannot be read."""
    ffprobe = shutil.which("ffprobe") or "ffprobe"
    cmd = [ffprobe, "-v", "error", "-show_entries", "format=duration",
           "-of", "csv=p=0", str(audio_path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if proc.returncode != 0:
            return 0
        return int(float(proc.stdout.decode().strip()) * 1000)
    except Exception:
        return 0


def _log(level, msg, *args):
    try:
        getattr(current_app.logger, level)(msg, *args)
    except RuntimeError:
        pass   # no app context (ingest script, shell)
