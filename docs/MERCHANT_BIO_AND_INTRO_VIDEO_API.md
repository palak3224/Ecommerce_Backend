# Merchant Bio & Intro Video API

Companion to [PROFILE_UPDATE_API.md](PROFILE_UPDATE_API.md). Covers the two
public-profile additions: a short **bio** and a single **intro video** with full
CRUD. Design rationale and rejected alternatives live in
[MERCHANT_BIO_AND_INTRO_VIDEO_PLAN.md](MERCHANT_BIO_AND_INTRO_VIDEO_PLAN.md).

> **Building a client?** Start with
> [MERCHANT_BIO_INTRO_VIDEO_INTEGRATION_GUIDE.md](MERCHANT_BIO_INTRO_VIDEO_INTEGRATION_GUIDE.md)
> instead — same endpoints, but with upload code, a UI state machine, error
> handling and the gotchas that bite integrators. This file is the terse
> reference.

---

## Bio

Stored on `merchant_profiles` (`bio`, `bio_link`, `bio_link_label`,
`bio_updated_at`). Distinct from `business_description`, which stays the
long-form "About" text.

### Rules

| Rule | Value |
|---|---|
| Max length | 250 **characters** (emoji count as 1) |
| Max lines | 5 |
| Format | plain text — HTML tags stripped, never rendered as HTML |
| Sanitisation | CRLF→LF, 3+ blank lines collapsed to 2, control/format chars (zero-width, RTL override) removed, trimmed |
| `bio_link` | http/https only, max 512 chars; a bare `example.com` is normalised to `https://example.com` |
| `bio_link_label` | max 60 chars; dropped automatically when there is no link |
| Clearing | send `""` or `null`; **omitting the key leaves the value unchanged** |

`javascript:`, `data:` and `vbscript:` links are rejected with a 400.

### Read — `GET /api/merchants/profile`

Adds to the existing `profile` object:

```jsonc
{
  "profile": {
    "…": "…",
    "bio": "Handmade brass décor from Moradabad ✨\nShips worldwide.",
    "bio_link": "https://example.com",
    "bio_link_label": "Our catalogue",
    "intro_video": { "…": "owner view, see below" }
  },
  "limits": {
    "bio_max_chars": 250,
    "bio_max_lines": 5,
    "bio_link_label_max_chars": 60,
    "intro_video": { "max_size_mb": 50, "max_duration_seconds": 60, "allowed_extensions": ["mov", "mp4"], "…": "…" }
  }
}
```

`limits` is published so the UI validates against the same numbers the server
enforces, instead of hardcoding a copy that drifts.

### Write — `PUT /api/merchants/profile`

```jsonc
// request
{ "bio": "Handmade brass décor ✨", "bio_link": "example.com", "bio_link_label": "Our catalogue" }

// 200
{ "message": "Profile updated successfully",
  "profile": { "…": "…", "bio": "Handmade brass décor ✨", "bio_link": "https://example.com", "bio_link_label": "Our catalogue" } }

// 400
{ "error": "Validation error",
  "details": { "bio": ["Bio must be 250 characters or fewer (got 312)."] } }
```

> **Note:** `business_phone` is still rejected. `UpdateProfileSchema` raises on
> unknown keys, so any client sending it gets a 400 for the whole request.

---

## Intro video

One active video per merchant, in `merchant_intro_videos`. All endpoints require
`@jwt_required()` + merchant role unless marked public.

### Limits

| Limit | Value | Note |
|---|---|---|
| Formats | `.mp4`, `.mov` | `webm` excluded — no iOS/Safari playback, no transcoding pipeline |
| Max size | 50 MB | hard limit; below the 100 MB `MAX_CONTENT_LENGTH` so oversize uploads get a JSON error, not a raw 413 |
| Max duration | 60 s | enforced in the browser always, and server-side **only when `ffprobe` is installed** — see below |
| Active videos | 1 per merchant | replace or delete to upload another |
| Uploads per day | 10 | counted in the database (`@rate_limit` is a no-op without Redis) |

**Duration is advisory server-side.** `ffprobe` is optional in this deployment.
When present, duration and resolution are measured and the 60 s cap is enforced
(`duration_verified: true`). When absent, the client-supplied
`duration_seconds` is stored as an unverified hint. **File size is the limit
that always holds.** The thumbnail is likewise best-effort — no ffmpeg means
`thumbnail_url: null`, and the player falls back to `preload="metadata"`.

### Object shape

Public subset (returned to shoppers):

```jsonc
{ "id": 12, "title": "Meet the maker", "caption": "A 40-second hello",
  "video_url": "https://cdn…/merchant-intro-videos/8/12-9f3a….mp4",
  "thumbnail_url": "https://cdn…/…_thumb.jpg",
  "duration_seconds": 42, "resolution": "1080x1920" }
```

Owner view adds `file_size_bytes`, `video_format`, `mime_type`,
`duration_verified`, `status`, `failure_reason`, `moderation_status`,
`moderation_notes`, `is_active`, `created_at`, `updated_at`. **These never
appear in a public response.**

### `GET /api/merchants/profile/intro-video`

Owner read. `200 {"intro_video": null, "limits": {…}}` when there is no video —
never a 404, because "not uploaded yet" is a normal state.

### `POST /api/merchants/profile/intro-video`

`multipart/form-data`: `video` (required), `title`, `caption`,
`duration_seconds` (client hint).

| Code | When |
|---|---|
| 201 | uploaded, `status: "ready"` |
| 400 | no/empty file, bad extension, magic-byte mismatch, over 50 MB, duration over 60 s (when measurable), title/caption too long |
| 401 / 403 | not authenticated / not a merchant |
| 404 | merchant profile not found |
| 409 | an active intro video already exists |
| 413 | request body exceeded `MAX_CONTENT_LENGTH` |
| 429 | daily upload cap reached |
| 500 | storage failure — the row is rolled back, nothing is persisted |

### `PUT /api/merchants/profile/intro-video`

JSON metadata only — `title`, `caption`, `is_active`. Never touches the stored
file. `is_active: false` hides the video from shoppers while keeping it.
`200` / `400` / `404`.

### `PUT /api/merchants/profile/intro-video/file`

Replace the file. Same multipart contract as create. The new object is uploaded
**before** the old one is deleted, so a failed upload leaves the current video
intact. `title`/`caption` survive unless overridden in the same request.
Moderation state resets. `200` / `400` / `404` / `429` / `500`.

### `DELETE /api/merchants/profile/intro-video`

Soft delete (row retained 30 days, then purged with its S3 objects by the
`INTRO_VIDEO_PURGE_ENABLED` job). `200`, or `404` when nothing active exists.

### Public reads

- `GET /api/merchants/<merchant_id>/intro-video` → `{"intro_video": … | null}`
- `GET /api/merchants/<merchant_id>/public-profile` → gains `intro_video`, `bio`,
  `bio_link`, `bio_link_label`, plus `username` and `profile_img` (previously
  missing).

Both return **`200` with `null`, never `404`**, when the video is hidden — a
status code must not reveal that a hidden or rejected video exists.

### Visibility rules

A video is public only when **all** of these hold:

| Level | Condition |
|---|---|
| Merchant | not soft-closed, deletion grace period not elapsed, user active (`MerchantProfile.is_publicly_visible()`) |
| Merchant | **verified** — `is_verified` and `verification_status == approved` (`is_public_media_visible()`) |
| Video | `deleted_at IS NULL`, `is_active`, `status == ready`, `moderation_status == approved` |

The bio uses only the first rule — text from an unverified merchant is no
riskier than the `business_description` they already publish. Prominent
unmoderated video is held to the stricter bar.

---

## Moderation (off by default)

`MERCHANT_INTRO_VIDEO_MODERATION_ENABLED=false` ships as the default, matching
reels: uploads are auto-approved. Setting it to `true` makes new and replaced
uploads `pending` — hidden from shoppers until a superadmin acts. **No migration
is needed to switch**; the column and the endpoints are already there.

- `GET /api/superadmin/merchant-intro-videos?moderation_status=pending&page=&per_page=`
- `POST /api/superadmin/merchant-intro-videos/<id>/approve`
- `POST /api/superadmin/merchant-intro-videos/<id>/reject` — body `{"reason": "…"}`, required

`GET /api/admin/merchants/<id>` also returns the merchant's bio and intro video
so the merchant-details screen can review them without a second call.

---

## Storage

Videos go to the **reels bucket** (`AWS_S3_REELS_BUCKET`, served via
`CLOUDFRONT_REELS_BASE_URL`) under a separate prefix, reusing the only
video-configured S3 path in the codebase:

```
merchant-intro-videos/{merchant_id}/{video_id}-{uuid}.mp4
merchant-intro-videos/{merchant_id}/{video_id}-{uuid}_thumb.jpg
```

The UUID means a replacement never reuses a URL, so objects are cached
`immutable` at the CDN with no staleness risk. A **rejected or deleted video
stays fetchable at its old URL until the CDN TTL expires** — the key is
unguessable and the API stops advertising it immediately. If legal takedown
becomes a requirement, add a CloudFront invalidation on delete/reject.

### Required IAM permissions

The intro video prefix is **new**, so an existing policy scoped to
`reels/*` will not cover it. Uploads fail with:

```
AccessDenied … not authorized to perform: s3:PutObject on resource:
"arn:aws:s3:::aoin-reels-prod/merchant-intro-videos/…"
```

Add this statement to the backend IAM user's policy (substitute your bucket):

```json
{
  "Sid": "MerchantIntroVideos",
  "Effect": "Allow",
  "Action": ["s3:PutObject", "s3:DeleteObject"],
  "Resource": "arn:aws:s3:::aoin-reels-prod/merchant-intro-videos/*"
}
```

`PutObject` covers the video and its thumbnail; `DeleteObject` is needed for
replace, delete and the purge job. `GetObject` is not required — CloudFront
serves the objects, the backend never reads them back.

Alternatively, widen an existing statement's resource from
`…/reels/*` to `…/*`.

---

## Config

| Variable | Default | Purpose |
|---|---|---|
| `MERCHANT_INTRO_VIDEO_MODERATION_ENABLED` | `false` | route uploads to a review queue |
| `INTRO_VIDEO_PURGE_ENABLED` | `true` | purge soft-deleted rows + S3 objects |
| `INTRO_VIDEO_PURGE_RETENTION_DAYS` | `30` | retention before purge |
| `INTRO_VIDEO_PURGE_INTERVAL_HOURS` | `24` | scheduler interval |

All three are disabled or inert under `TestingConfig`.

---

## Migration

`python init_db.py` runs `run_migration_010_merchant_bio_and_intro_video()`:
adds the four bio columns (explicit `utf8mb4` — emoji are 4-byte UTF-8 and fail
on a `utf8mb3` table), creates `merchant_intro_videos`, and creates the
`(merchant_id, deleted_at)` index. Idempotent and safe to re-run.

**Single-active is enforced in the controller**, not by a constraint: MySQL has
no partial unique index, so `UNIQUE(merchant_id)` cannot coexist with
soft-deleted history rows. Every write path takes a `SELECT … FOR UPDATE` row
lock before checking whether a video exists.
