"""
Tests for merchant intro video CRUD.

S3 is always mocked — no test may reach AWS. The fake service records what it
was asked to upload/delete so the tests can assert on cleanup behaviour.
"""
import io
from unittest.mock import patch

import pytest

from app import create_app
from common.database import db


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


class FakeS3:
    """Stand-in for MerchantIntroVideoS3Service."""

    def __init__(self, fail_upload=False):
        self.fail_upload = fail_upload
        self.uploaded = []
        self.deleted = []

    def upload_intro_video(self, file, merchant_id, video_id, file_extension='mp4'):
        if self.fail_upload:
            raise Exception("simulated S3 failure")
        key = f"merchant-intro-videos/{merchant_id}/{video_id}-abc.{file_extension}"
        self.uploaded.append(key)
        return {
            'url': f"https://cdn.test/{key}",
            's3_key': key,
            'bytes': 1234,
            'thumbnail_url': f"https://cdn.test/{key}_thumb.jpg",
            'thumbnail_s3_key': f"{key}_thumb.jpg",
        }

    def delete_intro_video(self, video_s3_key, thumbnail_s3_key=None):
        self.deleted.append(video_s3_key)
        return True


@pytest.fixture
def fake_s3():
    s3 = FakeS3()
    with patch(
        'controllers.merchant.merchant_intro_video_controller._s3_service',
        return_value=s3,
    ):
        yield s3


def _mk_merchant(email="merchant@ex.com", verified=True):
    from auth.models.models import User, UserRole, MerchantProfile
    from auth.models.merchant_document import VerificationStatus

    user = User(email=email, first_name="M", last_name="P", role=UserRole.MERCHANT,
                is_email_verified=True)
    user.set_password("StrongPass123")
    db.session.add(user)
    db.session.flush()

    profile = MerchantProfile(
        user_id=user.id,
        business_name="Brass Works",
        business_email=email,
        business_phone="9990001111",
        business_address="1 Main St",
        country_code="IN",
        state_province="UP",
        city="Moradabad",
        postal_code="244001",
    )
    if verified:
        profile.is_verified = True
        profile.verification_status = VerificationStatus.APPROVED
    db.session.add(profile)
    db.session.flush()
    return user, profile


def _auth(user_id):
    from flask_jwt_extended import create_access_token
    from auth.models.models import UserRole

    token = create_access_token(
        identity=str(user_id), additional_claims={"role": UserRole.MERCHANT.value}
    )
    return {"Authorization": f"Bearer {token}"}


def _mp4_bytes(size=2048):
    """Minimal ISO-BMFF header so the magic-byte check sees a real mp4."""
    header = b'\x00\x00\x00\x20ftypisom'
    return header + b'\x00' * max(0, size - len(header))


def _upload_payload(filename="intro.mp4", data=None, **extra):
    payload = {'video': (io.BytesIO(data or _mp4_bytes()), filename)}
    payload.update(extra)
    return payload


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #

def test_get_returns_null_when_no_video(client, app):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.get("/api/merchants/profile/intro-video", headers=_auth(uid))
    # Null, not 404: "no video yet" is a normal state.
    assert resp.status_code == 200
    assert resp.get_json()["intro_video"] is None
    assert resp.get_json()["limits"]["max_size_mb"] == 50


def test_upload_creates_ready_video(client, app, fake_s3):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.post(
        "/api/merchants/profile/intro-video",
        data=_upload_payload(title="Meet the maker", caption="Hello"),
        content_type='multipart/form-data',
        headers=_auth(uid),
    )
    assert resp.status_code == 201, resp.get_json()
    video = resp.get_json()["intro_video"]
    assert video["status"] == "ready"
    assert video["title"] == "Meet the maker"
    assert video["video_url"].startswith("https://cdn.test/")
    assert video["moderation_status"] == "approved"  # moderation off by default
    assert len(fake_s3.uploaded) == 1


def test_second_upload_conflicts(client, app, fake_s3):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                content_type='multipart/form-data', headers=_auth(uid))
    resp = client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                       content_type='multipart/form-data', headers=_auth(uid))
    assert resp.status_code == 409


def test_rejects_disallowed_extension(client, app, fake_s3):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.post(
        "/api/merchants/profile/intro-video",
        data=_upload_payload(filename="intro.webm"),
        content_type='multipart/form-data',
        headers=_auth(uid),
    )
    assert resp.status_code == 400
    assert not fake_s3.uploaded


@pytest.mark.parametrize(
    "payload",
    [
        b'<?php echo "hi"; ?>' + b'\x00' * 100,          # script renamed to .mp4
        b'MZ\x90\x00' + b'\x00' * 100,                    # Windows executable
        b'GIF89a' + b'\x00' * 100,                        # image renamed to .mp4
        b'\x1a\x45\xdf\xa3' + b'\x00' * 100,              # webm, deliberately unsupported
    ],
)
def test_rejects_non_video_content_with_video_extension(client, app, fake_s3, payload):
    """
    The extension says .mp4; the bytes say otherwise. Rejecting only on a
    *recognised wrong* type would let all of these through, because
    mimetypes.guess_type('intro.mp4') happily answers 'video/mp4'.
    """
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.post(
        "/api/merchants/profile/intro-video",
        data=_upload_payload(data=payload),
        content_type='multipart/form-data',
        headers=_auth(uid),
    )
    assert resp.status_code == 400
    assert not fake_s3.uploaded


def test_accepts_classic_quicktime_without_ftyp(client, app, fake_s3):
    """Older .mov files open on a bare atom rather than an ftyp box."""
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    data = b'\x00\x00\x00\x10moov' + b'\x00' * 200
    resp = client.post(
        "/api/merchants/profile/intro-video",
        data=_upload_payload(filename="intro.mov", data=data),
        content_type='multipart/form-data',
        headers=_auth(uid),
    )
    assert resp.status_code == 201, resp.get_json()


def test_rejects_empty_file(client, app, fake_s3):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.post(
        "/api/merchants/profile/intro-video",
        data={'video': (io.BytesIO(b''), 'intro.mp4')},
        content_type='multipart/form-data',
        headers=_auth(uid),
    )
    assert resp.status_code == 400


def test_rejects_oversize_file(client, app, fake_s3):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    # Shrink the cap rather than allocating 50MB in the test process.
    with patch(
        'controllers.merchant.merchant_intro_video_controller.MAX_VIDEO_SIZE', 1024
    ):
        resp = client.post(
            "/api/merchants/profile/intro-video",
            data=_upload_payload(data=_mp4_bytes(2048)),
            content_type='multipart/form-data',
            headers=_auth(uid),
        )
    assert resp.status_code == 400
    assert not fake_s3.uploaded


def test_upload_failure_leaves_no_row(client, app):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    failing = FakeS3(fail_upload=True)
    with patch(
        'controllers.merchant.merchant_intro_video_controller._s3_service',
        return_value=failing,
    ):
        resp = client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                           content_type='multipart/form-data', headers=_auth(uid))
    assert resp.status_code == 500

    # No half-written "processing" row left behind to block the next attempt.
    with app.app_context():
        from models.merchant_intro_video import MerchantIntroVideo

        assert MerchantIntroVideo.query.count() == 0


# --------------------------------------------------------------------------- #
# Update / replace / delete
# --------------------------------------------------------------------------- #

def test_update_metadata(client, app, fake_s3):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    client.post("/api/merchants/profile/intro-video", data=_upload_payload(title="Old"),
                content_type='multipart/form-data', headers=_auth(uid))
    resp = client.put("/api/merchants/profile/intro-video",
                      json={"title": "New title", "caption": "New caption"},
                      headers=_auth(uid))
    assert resp.status_code == 200
    assert resp.get_json()["intro_video"]["title"] == "New title"
    # Metadata edits must not touch the stored file.
    assert len(fake_s3.uploaded) == 1


def test_hide_removes_from_public_view(client, app, fake_s3):
    with app.app_context():
        user, profile = _mk_merchant()
        db.session.commit()
        uid, mid = user.id, profile.id

    client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                content_type='multipart/form-data', headers=_auth(uid))
    assert client.get(f"/api/merchants/{mid}/intro-video").get_json()["intro_video"] is not None

    client.put("/api/merchants/profile/intro-video", json={"is_active": False}, headers=_auth(uid))
    resp = client.get(f"/api/merchants/{mid}/intro-video")
    # 200 with null, never 404 — a hidden video must look like no video.
    assert resp.status_code == 200
    assert resp.get_json()["intro_video"] is None


def test_replace_uploads_new_and_deletes_old(client, app, fake_s3):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    client.post("/api/merchants/profile/intro-video", data=_upload_payload(title="Keep me"),
                content_type='multipart/form-data', headers=_auth(uid))
    old_key = fake_s3.uploaded[0]

    resp = client.put("/api/merchants/profile/intro-video/file", data=_upload_payload(),
                      content_type='multipart/form-data', headers=_auth(uid))
    assert resp.status_code == 200
    assert len(fake_s3.uploaded) == 2
    assert old_key in fake_s3.deleted
    # Metadata survives a file replacement unless explicitly overridden.
    assert resp.get_json()["intro_video"]["title"] == "Keep me"


def test_replace_without_existing_is_404(client, app, fake_s3):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.put("/api/merchants/profile/intro-video/file", data=_upload_payload(),
                      content_type='multipart/form-data', headers=_auth(uid))
    assert resp.status_code == 404


def test_delete_soft_deletes_and_allows_new_upload(client, app, fake_s3):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                content_type='multipart/form-data', headers=_auth(uid))
    resp = client.delete("/api/merchants/profile/intro-video", headers=_auth(uid))
    assert resp.status_code == 200

    with app.app_context():
        from models.merchant_intro_video import MerchantIntroVideo

        row = MerchantIntroVideo.query.first()
        assert row.deleted_at is not None  # soft, not hard
        assert row.is_active is False

    # Deleting frees the slot.
    resp = client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                       content_type='multipart/form-data', headers=_auth(uid))
    assert resp.status_code == 201


def test_delete_without_video_is_404(client, app, fake_s3):
    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    resp = client.delete("/api/merchants/profile/intro-video", headers=_auth(uid))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Public visibility
# --------------------------------------------------------------------------- #

def test_unverified_merchant_video_is_not_public(client, app, fake_s3):
    with app.app_context():
        user, profile = _mk_merchant(verified=False)
        db.session.commit()
        uid, mid = user.id, profile.id

    client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                content_type='multipart/form-data', headers=_auth(uid))

    # The owner still sees it...
    assert client.get("/api/merchants/profile/intro-video",
                      headers=_auth(uid)).get_json()["intro_video"] is not None
    # ...but shoppers do not.
    assert client.get(f"/api/merchants/{mid}/intro-video").get_json()["intro_video"] is None
    assert client.get(f"/api/merchants/{mid}/public-profile").get_json()["intro_video"] is None


def test_public_response_omits_moderation_fields(client, app, fake_s3):
    with app.app_context():
        user, profile = _mk_merchant()
        db.session.commit()
        uid, mid = user.id, profile.id

    client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                content_type='multipart/form-data', headers=_auth(uid))
    public = client.get(f"/api/merchants/{mid}/intro-video").get_json()["intro_video"]
    for leaked in ("moderation_status", "moderation_notes", "status", "failure_reason"):
        assert leaked not in public


def test_rejected_video_is_not_public(client, app, fake_s3):
    with app.app_context():
        user, profile = _mk_merchant()
        db.session.commit()
        uid, mid = user.id, profile.id

    client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                content_type='multipart/form-data', headers=_auth(uid))

    with app.app_context():
        from models.merchant_intro_video import MerchantIntroVideo, MODERATION_REJECTED

        row = MerchantIntroVideo.query.first()
        row.moderation_status = MODERATION_REJECTED
        db.session.commit()

    assert client.get(f"/api/merchants/{mid}/intro-video").get_json()["intro_video"] is None


def test_public_endpoint_for_unknown_merchant_returns_null(client, app):
    resp = client.get("/api/merchants/999999/intro-video")
    assert resp.status_code == 200
    assert resp.get_json()["intro_video"] is None


def test_moderation_flag_holds_video_for_review(client, app, fake_s3):
    with app.app_context():
        user, profile = _mk_merchant()
        db.session.commit()
        uid, mid = user.id, profile.id

    app.config['MERCHANT_INTRO_VIDEO_MODERATION_ENABLED'] = True
    resp = client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                       content_type='multipart/form-data', headers=_auth(uid))
    assert resp.get_json()["intro_video"]["moderation_status"] == "pending"
    assert client.get(f"/api/merchants/{mid}/intro-video").get_json()["intro_video"] is None


def test_daily_upload_cap(client, app, fake_s3):
    from controllers.merchant.merchant_intro_video_controller import MAX_UPLOADS_PER_DAY

    with app.app_context():
        user, _ = _mk_merchant()
        db.session.commit()
        uid = user.id

    # Upload + delete repeatedly so the single-active guard never trips.
    for _ in range(MAX_UPLOADS_PER_DAY):
        assert client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                           content_type='multipart/form-data',
                           headers=_auth(uid)).status_code == 201
        client.delete("/api/merchants/profile/intro-video", headers=_auth(uid))

    resp = client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                       content_type='multipart/form-data', headers=_auth(uid))
    assert resp.status_code == 429


def test_account_deletion_hides_intro_video(client, app, fake_s3):
    with app.app_context():
        user, profile = _mk_merchant()
        db.session.commit()
        uid, mid = user.id, profile.id

    client.post("/api/merchants/profile/intro-video", data=_upload_payload(),
                content_type='multipart/form-data', headers=_auth(uid))

    with app.app_context():
        from auth.models.models import MerchantProfile
        from services.merchant_account_deletion_service import finalize_merchant_profile

        finalize_merchant_profile(MerchantProfile.get_by_id(mid))

    assert client.get(f"/api/merchants/{mid}/intro-video").get_json()["intro_video"] is None
    assert client.get(f"/api/merchants/{mid}/public-profile").status_code == 404
