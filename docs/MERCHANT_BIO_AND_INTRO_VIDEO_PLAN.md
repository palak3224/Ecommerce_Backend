# Merchant Profile — Bio + Intro Video

Design record: the reasoning, constraints and rejected alternatives behind the
feature. **Status: implemented.** For the shipped API contract see
[MERCHANT_BIO_AND_INTRO_VIDEO_API.md](MERCHANT_BIO_AND_INTRO_VIDEO_API.md).

**Decisions taken** (the open questions in §6 below, resolved):

1. Public intro video — **verified merchants only**; bio public for any active merchant.
2. Moderation — **off at launch**, column + config flag shipped so it flips without a migration.
3. Bio length — **250 characters**.
4. Web surface — **API only**; nothing in `Ecommerce/src` consumes `/public-profile`, so the
   shopper-facing consumer is the mobile app. No storefront page was built. The merchant
   dashboard UI (upload/edit/delete) *was* built.
5. `webm` — **excluded**.

**Deviations from the plan below, and why:**

- **413 handler**: `app.py` already had a generic `HTTPException` → JSON handler, so oversize
  uploads were never returning HTML. A specific 413 handler was still added, for an actionable
  message instead of "exceeds the capacity limit".
- **Duration**: added a `duration_verified` column, not in the original plan. Without it there
  is no way to tell a measured duration from a client-supplied hint.
- **Phase 0 grew**: `handleSave` also had to stop sending empty strings, which fail the
  backend's length validators (`bank_account_number` requires 9–18 chars) and would 400 for
  any merchant without bank details.

Two additions to the merchant profile:

1. **Intro video** — one short self-introduction video per merchant, full CRUD by the merchant.
2. **Bio** — a short, Instagram-style public bio (text + optional link), separate from the existing long `business_description`.

---

## 1. Where this lands in the current code

Facts established by reading the repo — these drive every decision below.

| Thing | Location | Notes |
|---|---|---|
| Merchant model | [models.py:203](../auth/models/models.py#L203) `MerchantProfile`, table `merchant_profiles` | already has `profile_img`, `business_description`, `username` |
| Merchant self APIs | [api/merchants/routes.py](../api/merchants/routes.py), prefix `/api/merchants` ([app.py:378](../app.py#L378)) | `GET/PUT /profile`, `POST /profile/image` |
| Public merchant API | [api/merchants/routes.py:438](../api/merchants/routes.py#L438) `GET /api/merchants/<id>/public-profile` | today it does **not** return `profile_img` or `username` |
| Superadmin merchant view | [auth/admin_routes.py:251](../auth/admin_routes.py#L251) `GET /merchants/<id>` | where moderation UI reads from |
| Generic asset S3 | [services/s3_service.py](../services/s3_service.py) | bucket `AWS_S3_BUCKET_NAME`, CDN `CLOUDFRONT_ASSETS_BASE_URL`, has `upload_profile_image` / `_upload_asset_with_path` |
| Video S3 + thumbnails | [services/reels_s3_service.py](../services/reels_s3_service.py) | bucket `AWS_S3_REELS_BUCKET`, CDN `CLOUDFRONT_REELS_BASE_URL`, ffmpeg thumbnail generation (best-effort) |
| Video validation reference | [controllers/reels_controller.py:44-52](../controllers/reels_controller.py#L44-L52) | ext `{mp4, webm, mov}`, `MAX_VIDEO_SIZE = 100MB`, `MAX_VIDEO_DURATION = 60` (**declared but never enforced**) |
| Schema migration path | [init_db.py](../init_db.py), `run_migration_0XX_*` functions registered ~line 1559 | no working `flask db upgrade` in this repo |
| Merchant profile UI | [Profile.tsx](../../Ecommerce/src/pages/business/Profile.tsx) (885 lines) | inline `fetch`, no service layer |
| Superadmin merchant UI | `MerchantDetails` route `/superadmin/merchant-management/:id` ([App.tsx:489](../../Ecommerce/src/App.tsx#L489)) | |

### Three pre-existing landmines this work will hit

These are not caused by the new feature, but they sit directly in the code path and will make the new fields silently fail if not handled.

**(a) `UpdateProfileSchema` rejects unknown fields.** Marshmallow defaults to `unknown=RAISE`. `Profile.tsx` `handleSave` sends `business_phone` ([Profile.tsx:290](../../Ecommerce/src/pages/business/Profile.tsx#L290)), which is deliberately *not* declared in the schema ([routes.py:53](../api/merchants/routes.py#L53)). So `PUT /api/merchants/profile` returns `400 {"error":"Validation error","details":{"business_phone":["Unknown field."]}}` today — the web profile save is broken before we touch anything. **Fix as step 0**: drop `business_phone` from the FE payload (and either add `class Meta: unknown = EXCLUDE` or keep RAISE deliberately). Do not add `bio` on top of a 400.

**(b) Two allow-lists must both be edited.** A field passes marshmallow *and* must be in `allowed_fields` at [routes.py:760](../api/merchants/routes.py#L760), otherwise it is accepted, returns 200, and is silently dropped. Every new writable field goes in both places.

**(c) `business_description` is mis-wired on the FE.** [Profile.tsx:289](../../Ecommerce/src/pages/business/Profile.tsx#L289) sends `business_description: profileData.businessInfo.businessType` — the "business type" input overwrites the description. Fix while adding the bio field, since users will otherwise assume bio and description are the same broken box.

---

## 2. Bio

### 2.1 Why it is not `business_description`

`business_description` is **required at profile creation** ([routes.py:26](../api/merchants/routes.py#L26)), is `TEXT`, and reads as the long "About this business" block. An Instagram-style bio is a short, public, glanceable header line. Keep both:

- `business_description` → long form, About section, unchanged.
- `bio` → ≤ 250 chars, multi-line, emoji-friendly, shown under the merchant name in the profile header.

### 2.2 Columns (on `merchant_profiles`, no new table)

```python
bio            = db.Column(db.Text, nullable=True)            # ≤250 chars enforced in app layer
bio_link       = db.Column(db.String(512), nullable=True)     # single "link in bio", http(s) only
bio_link_label = db.Column(db.String(60), nullable=True)      # optional display text
bio_updated_at = db.Column(db.DateTime, nullable=True)
```

`Text` rather than `String(250)` so the limit is a product rule we can change without DDL, and so 4-byte emoji never truncate mid-character at the DB layer.

### 2.3 Validation rules (server-side, authoritative)

| Rule | Value | Reason |
|---|---|---|
| Max length | 250 **characters** (`len(str)`, not bytes) | emoji are 1 char, 4 bytes — never count bytes |
| Max lines | 5 (`\n` count ≤ 4) | keeps the header from ballooning |
| Newline normalisation | `\r\n` and `\r` → `\n`, collapse 3+ consecutive `\n` to 2 | |
| Trim | leading/trailing whitespace stripped | |
| Control chars | strip everything in `Cc`/`Cf` except `\n` (kills zero-width + RTL-override tricks) | |
| HTML | strip tags entirely; bio is **plain text**, never rendered as HTML | XSS |
| Clearing | explicit `null` or `""` clears the field; key absent = unchanged | |
| `bio_link` | must parse as absolute URL with scheme in `{http, https}`; max 512 chars; reject `javascript:`, `data:`, `vbscript:` | XSS via link |
| `bio_link_label` | ≤ 60 chars, plain text, ignored if `bio_link` is null | |

Rendering rules (frontend, section 5.2): `@mentions` / `#hashtags` are **displayed as plain text, not linkified**, in v1 — there is no merchant mention graph to link to and linkifying invites spam.

### 2.4 API — extend the existing endpoints, no new ones

`GET /api/merchants/profile` gains three keys:

```jsonc
{ "profile": { "...": "...", "bio": "Handmade brass décor…", "bio_link": "https://example.com", "bio_link_label": "Our catalogue" } }
```

`PUT /api/merchants/profile` accepts them:

```jsonc
// request
{ "bio": "Handmade brass décor from Moradabad ✨\nShips worldwide.", "bio_link": "https://example.com", "bio_link_label": "Our catalogue" }
// 200
{ "message": "Profile updated successfully", "profile": { "bio": "…", "bio_link": "…", "bio_link_label": "…" } }
// 400
{ "error": "Validation error", "details": { "bio": ["Bio must be 250 characters or fewer (got 312)."] } }
```

Changes required: add `bio` / `bio_link` / `bio_link_label` to `UpdateProfileSchema`, to `allowed_fields` (landmine **b**), to the `GET /profile` response dict at [routes.py:399](../api/merchants/routes.py#L399), and set `bio_updated_at` when `bio` changes.

**Public exposure** — `GET /api/merchants/<id>/public-profile` returns `bio`, `bio_link`, `bio_link_label` only when the merchant is publicly visible (section 4.3). While we are in this endpoint, also add `profile_img` and `username`, which it inexplicably omits today.

---

## 3. Intro video

### 3.1 Storage shape — dedicated table, not columns

Recommended: **`merchant_intro_videos` table**, one active row per merchant.

Rationale: the ask is "all CRUD operations," which means replace and delete are first-class. With columns on `merchant_profiles`, a failed replace leaves the profile row half-written and the old S3 object orphaned with nothing recording it. A row gives us an upload lifecycle (`processing → ready/failed`), a moderation state, soft delete, and an audit trail for the S3 cleanup job — at the cost of one extra table and one join.

The cheaper alternative (5 columns on `merchant_profiles`, hard-replace) is viable if you want the smallest diff; it costs you the moderation trail and safe rollback. **Recommendation: the table.**

```python
class MerchantIntroVideo(BaseModel):
    __tablename__ = 'merchant_intro_videos'

    id                = db.Column(db.Integer, primary_key=True)
    merchant_id       = db.Column(db.Integer, db.ForeignKey('merchant_profiles.id'), nullable=False, index=True)

    title             = db.Column(db.String(120), nullable=True)
    caption           = db.Column(db.String(500), nullable=True)

    video_url         = db.Column(db.String(512), nullable=True)   # null while status='processing'
    video_s3_key      = db.Column(db.String(512), nullable=True)
    thumbnail_url     = db.Column(db.String(512), nullable=True)   # null if ffmpeg unavailable
    thumbnail_s3_key  = db.Column(db.String(512), nullable=True)

    duration_seconds  = db.Column(db.Integer, nullable=True)       # best-effort, see 6.2
    file_size_bytes   = db.Column(db.BigInteger, nullable=True)
    video_format      = db.Column(db.String(10), nullable=True)    # mp4 | mov
    mime_type         = db.Column(db.String(60), nullable=True)
    resolution        = db.Column(db.String(20), nullable=True)    # "1080x1920"

    status            = db.Column(db.String(20), nullable=False, default='processing')  # processing|ready|failed
    failure_reason    = db.Column(db.String(255), nullable=True)

    moderation_status = db.Column(db.String(20), nullable=False, default='approved')     # pending|approved|rejected
    moderation_notes  = db.Column(db.String(500), nullable=True)
    moderated_at      = db.Column(db.DateTime, nullable=True)
    moderated_by      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    is_active         = db.Column(db.Boolean, nullable=False, default=True)   # merchant's own show/hide toggle
    created_at        = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at        = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at        = db.Column(db.DateTime, nullable=True, index=True)
```

`moderation_status` defaults to `approved`, matching how reels ship today ([reels_controller.py](../controllers/reels_controller.py) creates reels with `approval_status='approved'`). Flip the default to `pending` with a config flag (`MERCHANT_INTRO_VIDEO_MODERATION_ENABLED`) when a review queue exists — do not build the queue in v1.

**Single-active enforcement.** MySQL has no partial unique index, so `UNIQUE(merchant_id)` cannot coexist with soft-deleted history rows. Enforce in the controller: every write path opens a transaction and does `SELECT … WHERE merchant_id=:id AND deleted_at IS NULL FOR UPDATE` before inserting. Add a non-unique index `(merchant_id, deleted_at)`.

**Public visibility predicate** (one place, one helper, used by every public read):

```
deleted_at IS NULL AND is_active = 1 AND status = 'ready' AND moderation_status = 'approved'
AND merchant is publicly visible  (section 4.3)
```

### 3.2 Limits

| Limit | Value | Why this number |
|---|---|---|
| Max file size | **50 MB** | `MAX_CONTENT_LENGTH` is 100 MB ([app.py:130](../app.py#L130)); a 100 MB file plus multipart overhead trips Werkzeug's 413 *before* any handler runs, returning HTML, not JSON. 50 MB leaves clear headroom. |
| Max duration | **60 s** | matches the reels product rule; enforced client-side always, server-side only when ffprobe is available (6.2) |
| Formats | **`.mp4` and `.mov` only** | `webm` does not play in Safari/iOS, and there is no transcoding pipeline in this repo. Accepting it would ship videos that a large share of shoppers cannot watch. |
| MIME | `video/mp4`, `video/quicktime`, verified against magic bytes, not just the extension | |
| Videos per merchant | 1 active | |
| Uploads per merchant per day | 10 (counted from `created_at` rows) | `@rate_limit` degrades to a no-op without Redis ([common/cache.py](../common/cache.py)), so the DB count is the real guard |
| Retained soft-deleted rows | 30 days, then a purge job deletes rows + S3 objects | |

### 3.3 Where the bytes go

Use **`reels_s3_service`'s bucket and CDN**, with a distinct key prefix — it is the only video-configured path in the codebase (correct `ContentType`, multipart upload, ffmpeg thumbnails, CloudFront URL generation). Adding video handling to `s3_service` (the image/asset bucket) would duplicate all of it.

```
s3://$AWS_S3_REELS_BUCKET/merchant-intro-videos/{merchant_id}/{uuid}.mp4
s3://$AWS_S3_REELS_BUCKET/merchant-intro-videos/{merchant_id}/{uuid}_thumb.jpg
→ https://$CLOUDFRONT_REELS_BASE_URL/merchant-intro-videos/{merchant_id}/{uuid}.mp4
```

New methods on `ReelsS3Service` (or a thin `MerchantIntroVideoS3Service` wrapping it): `upload_intro_video(file, merchant_id, video_id)`, `delete_intro_video(s3_key, thumbnail_s3_key)`. Reuse `_generate_and_upload_thumbnail` unchanged.

Set on upload: `ContentType` from the detected MIME, `ContentDisposition: inline`, `CacheControl: public, max-age=31536000, immutable` (safe — keys are UUID-unique, so a replacement is never the same URL).

### 3.4 Upload strategy

**v1: server-proxied multipart upload** (browser → Flask → S3), identical to reels. Simple, consistent, one round trip, and validation happens before a single byte reaches the bucket.

Known cost: a 50 MB upload occupies a waitress worker for the duration. At the current merchant volume — one video per merchant, uploaded once — this is acceptable. **Upgrade path if worker starvation shows up:** presigned `PUT` direct to S3 (`POST /intro-video/upload-url` → browser PUTs → `POST /intro-video/confirm` validates size/MIME via `head_object` and flips `status` to `ready`). The `status` column already exists precisely so this swap is additive.

### 3.5 API

All merchant endpoints: `@jwt_required()` + `@merchant_role_required`, under `/api/merchants/profile/intro-video`.

---

**`POST /api/merchants/profile/intro-video`** — create

`multipart/form-data`: `video` (file, required), `title` (≤120, optional), `caption` (≤500, optional), `duration_seconds` (int, optional client hint).

```jsonc
// 201
{
  "message": "Intro video uploaded successfully",
  "intro_video": {
    "id": 12, "title": "Meet the maker", "caption": "…",
    "video_url": "https://cdn…/merchant-intro-videos/8/9f3a….mp4",
    "thumbnail_url": "https://cdn…/…_thumb.jpg",
    "duration_seconds": 42, "file_size_bytes": 18234221,
    "video_format": "mp4", "resolution": "1080x1920",
    "status": "ready", "moderation_status": "approved",
    "is_active": true, "created_at": "2026-08-05T10:00:00Z", "updated_at": "2026-08-05T10:00:00Z"
  }
}
```

| Code | When |
|---|---|
| 400 | no file / empty file / bad extension / bad magic bytes / over 50 MB / duration > 60 s (when measurable) / title or caption too long |
| 401 | missing or invalid JWT |
| 403 | not a merchant |
| 404 | merchant profile not found |
| 409 | an active intro video already exists → *"Delete or replace the existing intro video first."* |
| 413 | request body exceeded `MAX_CONTENT_LENGTH` (needs the JSON error handler in 6.1) |
| 429 | daily upload cap hit |
| 500 | S3 upload failed (row rolled back, nothing persisted) |

---

**`GET /api/merchants/profile/intro-video`** — owner read. Returns the full object including `status`, `moderation_status`, `moderation_notes`, `failure_reason`. `200 {"intro_video": null}` when none exists — **not** a 404; the "no video yet" state is normal and the FE should not have to treat it as an error.

---

**`PUT /api/merchants/profile/intro-video`** — metadata only, `application/json`

```jsonc
{ "title": "Meet the maker", "caption": "A 40-second hello", "is_active": true }
```

Never touches the file. `200` with the updated object; `404` if no active video; `400` on validation.

---

**`PUT /api/merchants/profile/intro-video/file`** — replace the file

Same `multipart/form-data` contract as create. Uploads the new object first, flips the row to the new keys, then best-effort deletes the old S3 objects; a delete failure is logged, never fatal (the row keeps `status='ready'` and the orphan is swept by the purge job). Metadata (`title`, `caption`, `is_active`) is preserved unless overridden in the same request. Resets `moderation_status` to the configured default. `200` / `404` / same 400s as create.

---

**`DELETE /api/merchants/profile/intro-video`** — soft delete

Sets `deleted_at`, `is_active = false`; best-effort S3 delete. `200 {"message": "Intro video deleted successfully"}`; `404` when nothing active exists (not idempotent-200 — a 404 here is a real signal that the client's state is stale).

---

**Public reads**

- `GET /api/merchants/<merchant_id>/public-profile` — gains an `intro_video` key: the public subset (`id`, `title`, `caption`, `video_url`, `thumbnail_url`, `duration_seconds`, `resolution`) or `null`. No moderation fields ever leak here.
- `GET /api/merchants/<merchant_id>/intro-video` — standalone public read, same subset, for clients that only need the video. `200 {"intro_video": null}` when hidden or absent — **never 404**, so a hidden video is indistinguishable from no video.

**Superadmin (phase 4, only if moderation is turned on)**

- `GET /api/superadmin/merchant-intro-videos?moderation_status=pending&page=&per_page=`
- `POST /api/superadmin/merchant-intro-videos/<id>/approve`
- `POST /api/superadmin/merchant-intro-videos/<id>/reject` → `{ "reason": "…" }` (required, ≤500)

Existing `GET /merchants/<id>` in [auth/admin_routes.py:251](../auth/admin_routes.py#L251) also returns the merchant's bio + intro video so the merchant-details screen shows them without a second call.

### 3.6 Upload flow, step by step

```
FE  ─ validate type, size ≤50MB, duration ≤60s (HTMLVideoElement metadata), then POST multipart
BE  ─ 1. auth → resolve MerchantProfile (404 if none)
      2. daily upload count < 10                                    → else 429
      3. SELECT … FOR UPDATE on active row                          → 409 if one exists (create path)
      4. extension in {mp4, mov}                                    → else 400
      5. size: 0 < n ≤ 50MB                                         → else 400
      6. magic-byte MIME check (reels_controller.py:376-405 pattern) → else 400
      7. INSERT row status='processing'  (db.session.flush → id)
      8. upload video to S3
      9. generate + upload thumbnail (ffmpeg, best-effort, never fatal)
     10. UPDATE row: urls, keys, size, format, resolution, status='ready'
     11. COMMIT
     ── any failure at 8/10 → ROLLBACK, best-effort S3 cleanup, 500 STORAGE_ERROR
```

Never `commit()` the `processing` row before the S3 upload: a crash mid-upload would leave a permanently-processing row that blocks the merchant's next attempt with a 409.

---

## 4. Limitations and edge cases

### 4.1 Request-size ceiling (highest-risk item)

`MAX_CONTENT_LENGTH = 100 MB` is enforced by Werkzeug *before* the view function runs. A file above it produces Flask's **HTML** 413 page, which the FE's `res.json()` call will choke on with a confusing parse error. Two required mitigations: cap the video at 50 MB in the validator, and register a JSON 413 handler in `create_app`:

```python
@app.errorhandler(413)
def _payload_too_large(_e):
    return jsonify({"error": "File too large. Maximum upload size is 50MB."}), 413
```

This also fixes the same latent problem for product media and reels.

### 4.2 Duration cannot be trusted, and ffmpeg may be absent

`MAX_VIDEO_DURATION = 60` in `reels_controller.py` is declared and **never checked** — there is no server-side duration enforcement anywhere in this codebase today. `reels_s3_service` locates ffmpeg via `shutil.which` and degrades gracefully when it is missing, so we cannot assume it exists in every environment.

Approach: FE reads duration from `HTMLVideoElement.duration` and blocks > 60 s. BE runs `ffprobe` **only if the binary resolves**, and enforces the limit when it does. When it does not, store the client-supplied `duration_seconds` as an unverified hint. Document that duration is advisory server-side; the 50 MB size cap is the hard limit that always holds.

Consequence: no thumbnail when ffmpeg is missing. The FE must render `<video preload="metadata">` with no poster rather than a broken image.

### 4.3 Merchant states that must hide public content

The public predicate must exclude a merchant when **any** of these holds — the existing `public-profile` endpoint already checks the first three ([routes.py:507-512](../api/merchants/routes.py#L507-L512)) and the new endpoints must not diverge:

- `merchant_profile.account_deleted_at IS NOT NULL` (soft-closed)
- `merchant_profile.account_deletion_effective_at` has passed
- `user.is_active = false` (suspended)
- `verification_status != approved` — **decision needed**: should an unverified merchant's bio and intro video be publicly visible? Recommendation: **no** for the video (it is prominent, unmoderated media), **yes** for the bio (text, already true of `business_description`). Whatever is chosen, put it in one helper — `MerchantProfile.is_publicly_visible()` — and call it from every public read.

Also wire the video into [merchant_account_deletion_service.py](../services/merchant_account_deletion_service.py): when the grace period expires, soft-delete the intro video row and purge the S3 objects along with the rest of the sweep.

### 4.4 Concurrency and orphans

- **Double-click / double-submit** → two rows and two S3 objects. Guarded by the `FOR UPDATE` lock plus a disabled submit button. Without the lock, `SELECT`-then-`INSERT` races cleanly through.
- **Replace where the old S3 delete fails** → orphaned object, still referenced nowhere. Logged; swept by the purge job. Never fail the request for this.
- **Delete during moderation** → soft delete wins; the moderation endpoint returns 404 for a deleted row.
- **Purge job** — a new APScheduler task (gated by `INTRO_VIDEO_PURGE_ENABLED`, disabled under `TestingConfig`, following the pattern of the existing cleanup jobs in `create_app`) that deletes soft-deleted rows older than 30 days plus their S3 objects.

### 4.5 CDN caching

CloudFront caches the video for its TTL. Because keys are UUID-based, a replacement always gets a new URL, so there is no stale-content problem. But a **rejected or deleted** video remains fetchable at its old URL until the TTL expires. The key is unguessable and the API stops advertising it immediately, which is adequate for public marketing content; if legal takedown is a requirement, add a CloudFront invalidation call on delete/reject. Note it, do not build it in v1.

### 4.6 Emoji and character-set

Instagram-style bios will contain emoji, which are 4-byte UTF-8. If `merchant_profiles` (or the DB default) is `utf8mb3`, inserting an emoji throws `Incorrect string value`. **Verify before shipping:**

```sql
SELECT table_collation FROM information_schema.tables
 WHERE table_schema = DATABASE() AND table_name = 'merchant_profiles';
```

If it is not `utf8mb4_*`, the migration must add the columns as `TEXT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci` explicitly (converting the whole table is riskier and not necessary for new columns). Also confirm the SQLAlchemy connection string carries `?charset=utf8mb4`.

### 4.7 Security

- **Bio XSS** — plain text end to end. React escapes by default; the only rule is *never* `dangerouslySetInnerHTML` on bio. Server still strips tags as defence in depth.
- **Link scheme** — `bio_link` restricted to `http`/`https`. Render with `target="_blank" rel="noopener noreferrer nofollow"`.
- **Video content** — no automated content scanning exists in this repo. Unmoderated merchant video is a real trust-and-safety exposure; the `moderation_status` column and the config flag exist so the queue can be switched on without a migration. Flag this to whoever owns policy.
- **MIME spoofing** — magic bytes, not the extension (reuse the reels byte-header checks).
- **IDOR** — every merchant endpoint resolves the row by `merchant_id` from the JWT, never from a client-supplied id.

### 4.8 Compatibility

- Response fields are **additive only**. `/api/merchants/profile` is consumed by the mobile app (`api/merchants/`) — do not rename or reorder anything existing.
- Old clients ignore the new keys; new clients must treat `intro_video: null` and `bio: null` as normal.
- No CORS changes: the API origin is unchanged. The CloudFront video host is a media URL, not an XHR target, so `ALLOWED_ORIGINS` needs nothing.

### 4.9 Testing constraints

`tests/conftest.py` uses `create_app("testing")` → in-memory SQLite, no MySQL, no Redis. So:

- S3 must be mocked (patch `get_reels_s3_service`); no test may hit AWS.
- SQLite accepts the model DDL but not the raw MySQL `ALTER TABLE`/`information_schema` statements in `init_db.py` — migration code is exercised manually against MySQL, not in pytest.
- Emoji/charset behaviour cannot be tested on SQLite (it is UTF-8 throughout). Verify manually against MySQL.

---

## 5. Work breakdown

### Phase 0 — unblock the existing endpoint (~30 min)
1. Remove `business_phone` from the `handleSave` payload in `Profile.tsx`.
2. Fix `business_description` mapping (landmine **c**).
3. Manually verify `PUT /api/merchants/profile` returns 200.

### Phase 1 — bio, backend
4. Add 4 columns to `MerchantProfile`.
5. `run_migration_010_merchant_bio_and_intro_video()` in `init_db.py` — idempotent column adds with explicit `utf8mb4`; register it in the runner list (~line 1559).
6. Add a `validate_bio()` helper (sanitisation rules from 2.3) + `bio_link` scheme validation.
7. Extend `UpdateProfileSchema`, `allowed_fields`, `GET /profile` response, and the `public-profile` response (plus `profile_img` / `username` there).

### Phase 2 — intro video, backend
8. `models/merchant_intro_video.py`; import it in `init_db.py` so `db.create_all()` picks it up; extend migration 010 with the `CREATE TABLE` guard.
9. `upload_intro_video` / `delete_intro_video` on the reels S3 service.
10. `controllers/merchant/merchant_intro_video_controller.py` — validation constants, the 6 operations, the `FOR UPDATE` single-active guard, the daily cap.
11. `routes/merchant_intro_video_routes.py` (or extend `api/merchants/routes.py` to keep `/api/merchants/profile/*` in one file — **preferred**, it is the same URL family). Swagger docstrings per house style.
12. JSON 413 handler + `MERCHANT_INTRO_VIDEO_*` config flags in `config.py`.

### Phase 3 — frontend, merchant dashboard
13. `src/services/merchantProfileApi.ts` — six typed calls in one place. Justified here despite the inline-`fetch` convention: `Profile.tsx` is already 885 lines and this adds multipart + progress + error mapping.
14. `src/components/business/profile/BioSection.tsx` — textarea, live "N/250" counter that turns red past the limit, link + label inputs, inline validation mirroring the server rules exactly.
15. `src/components/business/profile/IntroVideoSection.tsx` — empty state, upload with a progress bar, `<video controls preload="metadata" playsinline>` preview with poster, edit title/caption, show/hide toggle, replace, delete-with-confirm, and explicit rendering of `status='failed'` / `moderation_status='rejected'` with the reason.
16. Wire both into `Profile.tsx` under the existing edit-mode pattern; `toast` for feedback, matching the file.

### Phase 4 — public surface + moderation (optional)
17. **Open question:** no web page currently consumes `/public-profile` — nothing in `Ecommerce/src` references it. As things stand the bio and video would be **mobile-app-only**. If they should appear on the web, a merchant storefront page has to be built or an existing product page extended. *Needs a product decision before this phase is scoped.*
18. Superadmin moderation endpoints + a panel on `MerchantDetails`, only if moderation is switched on.

### Phase 5 — hardening
19. Purge job for soft-deleted videos + orphaned S3 objects.
20. `tests/test_merchant_bio.py` and `tests/test_merchant_intro_video.py` (S3 mocked): validation limits, 409 on duplicate, replace flow, soft delete, public-visibility predicate across every merchant state in 4.3.
21. Document both features in `docs/PROFILE_UPDATE_API.md` (it already covers merchant profile updates and will otherwise go stale).

---

## 6. Decisions needed before implementation starts

1. **Verified-merchants-only for the public intro video?** (recommendation: yes for video, no for bio)
2. **Moderation on or off at launch?** (recommendation: off, matching reels; the column and flag ship either way)
3. **Bio length — 250 chars, or 150 to match Instagram exactly?** (recommendation: 250; merchants write business copy, not personal bios)
4. **Where does this show up on the web?** (see 4.17 — currently nowhere; may be mobile-only by design)
5. **`webm` really excluded?** (recommendation: yes — no transcoding pipeline, and it does not play on iOS Safari)
