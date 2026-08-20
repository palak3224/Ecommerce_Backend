# services/music/song_upload_service.py
"""Put an uploaded audio file on S3 and turn it into a catalogue row.

This is the primary way songs arrive, not a convenience. Downloading a track from
Pixabay gives you a file on a laptop, not a URL — so a URL-only admin form would
mean uploading the file somewhere else first just to paste a link back in. The
file *is* what an admin has.

Mirrors the reels S3 service: same bucket, its own prefix, CloudFront in front.
"""
import os
import tempfile
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import current_app
from werkzeug.utils import secure_filename

from services.music.waveform_service import (
    audio_tooling_available, generate_peaks, probe_duration_ms,
)


ALLOWED_EXTENSIONS = {"mp3", "m4a", "aac", "wav", "ogg", "flac"}
MAX_UPLOAD_BYTES = 30 * 1024 * 1024      # 30MB — a long track at a sane bitrate

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024

IMAGE_CONTENT_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png", "webp": "image/webp",
}

CONTENT_TYPES = {
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
}


class SongUploadError(Exception):
    """The file could not be taken. Message is admin-facing."""


def _s3_error_message(error, key):
    """Turn an S3 failure into something that names the actual problem.

    "Could not store the audio file" sends an admin off re-exporting an mp3 that
    was never the issue. A denied PutObject is a policy scoped to the wrong
    prefix, and saying so is the difference between a five minute fix and an
    afternoon.
    """
    code = ""
    if isinstance(error, ClientError):
        code = error.response.get("Error", {}).get("Code", "")

    if code in ("AccessDenied", "AllAccessDisabled", "InvalidAccessKeyId",
                "SignatureDoesNotMatch"):
        prefix = key.split("/")[0] if "/" in key else key
        return (
            f"Storage rejected the upload: the server's AWS credentials are not "
            f"allowed to write to the '{prefix}/' folder of the media bucket. "
            f"Either grant s3:PutObject on that prefix, or point "
            f"AWS_S3_MUSIC_PREFIX at a folder the policy already permits."
        )
    if code == "NoSuchBucket":
        return "Storage rejected the upload: the media bucket does not exist."
    return "Could not store the file. Please check the server logs."


def _config():
    bucket = os.getenv("AWS_S3_REELS_BUCKET", "aoin-reels-prod")
    region = os.getenv("AWS_REGION", "ap-south-1")
    cdn = (os.getenv("CLOUDFRONT_REELS_BASE_URL") or "").rstrip("/")
    prefix = os.getenv("AWS_S3_MUSIC_PREFIX", "music/").strip("/")
    if not cdn:
        raise SongUploadError("CLOUDFRONT_REELS_BASE_URL is not configured.")
    return bucket, region, cdn, prefix


def _client(region):
    return boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def _extension(filename):
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise SongUploadError(
            f"Unsupported audio format {ext or '(none)'}. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )
    return ext


def upload_song_file(file_storage):
    """Store the file and analyse it.

    Returns {audio_url, s3_key, duration_ms, waveform_peaks, size_bytes}.

    The file is written to a temp path first so ffmpeg can measure it. Length and
    waveform come from the actual audio rather than anything the uploader typed,
    because a wrong duration silently breaks the trim window on every phone.
    """
    if not file_storage or not file_storage.filename:
        raise SongUploadError("No file was uploaded.")

    ext = _extension(secure_filename(file_storage.filename))
    bucket, region, cdn, prefix = _config()

    fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}")
    os.close(fd)
    try:
        file_storage.save(tmp_path)
        size = os.path.getsize(tmp_path)
        if size == 0:
            raise SongUploadError("The uploaded file is empty.")
        if size > MAX_UPLOAD_BYTES:
            raise SongUploadError(
                f"File is {size // (1024 * 1024)}MB; the limit is "
                f"{MAX_UPLOAD_BYTES // (1024 * 1024)}MB."
            )

        duration_ms = probe_duration_ms(tmp_path)
        if duration_ms <= 0:
            # Distinguish "the server cannot measure anything" from "this file is
            # not audio". The first is an ops problem and blaming the file for it
            # sends an admin off re-exporting a perfectly good mp3.
            if not audio_tooling_available():
                current_app.logger.error(
                    "Song upload: neither ffmpeg nor ffprobe is installed"
                )
                raise SongUploadError(
                    "Audio processing is not available on this server "
                    "(ffmpeg is not installed). Please contact support."
                )
            raise SongUploadError(
                "This file does not look like playable audio."
            )

        peaks = generate_peaks(tmp_path)

        key = f"{prefix}/{uuid.uuid4().hex}.{ext}"
        try:
            _client(region).upload_file(
                tmp_path, bucket, key,
                ExtraArgs={
                    "ContentType": CONTENT_TYPES.get(ext, "audio/mpeg"),
                    # Catalogue audio is immutable — a new track is a new key — so
                    # it can be cached hard.
                    "CacheControl": "public, max-age=31536000, immutable",
                },
            )
        except (BotoCoreError, ClientError) as e:
            current_app.logger.error("Song upload to S3 failed: %s", e, exc_info=True)
            raise SongUploadError(_s3_error_message(e, key))

        return {
            "audio_url": f"{cdn}/{key}",
            "s3_key": key,
            "duration_ms": duration_ms,
            "waveform_peaks": peaks,
            "size_bytes": size,
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def upload_artwork_file(file_storage):
    """Store a cover image and return its URL.

    Same reasoning as the audio: an admin who downloaded a track also downloaded
    its cover, so asking for a URL means finding somewhere to host it first.
    """
    if not file_storage or not file_storage.filename:
        return None

    name = secure_filename(file_storage.filename)
    ext = (name.rsplit(".", 1)[-1] if "." in name else "").lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise SongUploadError(
            f"Unsupported image format {ext or '(none)'}. "
            f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}."
        )

    bucket, region, cdn, prefix = _config()

    fd, tmp_path = tempfile.mkstemp(suffix=f".{ext}")
    os.close(fd)
    try:
        file_storage.save(tmp_path)
        size = os.path.getsize(tmp_path)
        if size == 0:
            raise SongUploadError("The artwork file is empty.")
        if size > MAX_IMAGE_BYTES:
            raise SongUploadError(
                f"Artwork is {size // (1024 * 1024)}MB; the limit is "
                f"{MAX_IMAGE_BYTES // (1024 * 1024)}MB."
            )

        key = f"{prefix}/artwork/{uuid.uuid4().hex}.{ext}"
        try:
            _client(region).upload_file(
                tmp_path, bucket, key,
                ExtraArgs={
                    "ContentType": IMAGE_CONTENT_TYPES.get(ext, "image/jpeg"),
                    "CacheControl": "public, max-age=31536000, immutable",
                },
            )
        except (BotoCoreError, ClientError) as e:
            current_app.logger.error("Artwork upload failed: %s", e, exc_info=True)
            raise SongUploadError(_s3_error_message(e, key))

        return f"{cdn}/{key}"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
