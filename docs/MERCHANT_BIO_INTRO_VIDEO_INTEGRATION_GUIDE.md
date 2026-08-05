# Merchant Bio & Intro Video — Frontend / App Integration Guide

Everything a web or mobile developer needs to integrate the merchant **bio** and
**intro video** features. Self-contained: you should not need to read the
backend source.

- Design rationale → [MERCHANT_BIO_AND_INTRO_VIDEO_PLAN.md](MERCHANT_BIO_AND_INTRO_VIDEO_PLAN.md)
- Terse API reference → [MERCHANT_BIO_AND_INTRO_VIDEO_API.md](MERCHANT_BIO_AND_INTRO_VIDEO_API.md)
- Working web implementation → `Ecommerce/src/services/merchantProfileApi.ts`,
  `Ecommerce/src/components/business/profile/`

---

## Contents

1. [Basics](#1-basics)
2. [Feature overview](#2-feature-overview)
3. [Bio API](#3-bio-api)
4. [Intro video API](#4-intro-video-api)
5. [Public (shopper-facing) API](#5-public-shopper-facing-api)
6. [Error handling](#6-error-handling)
7. [UI state machine for the intro video](#7-ui-state-machine-for-the-intro-video)
8. [Integration recipes](#8-integration-recipes)
9. [Gotchas — read this before you start](#9-gotchas--read-this-before-you-start)
10. [Quick reference](#10-quick-reference)

---

## 1. Basics

**Base URL**

```
{API_BASE_URL}/api/merchants
```

Web reads `API_BASE_URL` from `import.meta.env.VITE_API_BASE_URL`. Mobile should
use the same host.

**Authentication**

Every merchant-owned endpoint needs a merchant JWT:

```
Authorization: Bearer <access_token>
```

On web the token lives in `localStorage.getItem('access_token')`. Endpoints
marked **Public** take no auth.

**Content types**

| Operation | Content-Type |
|---|---|
| Bio updates, video metadata updates | `application/json` |
| Video upload / replace | `multipart/form-data` |

Do **not** set `Content-Type` manually on multipart requests — let the HTTP
client set it, so the boundary is generated correctly.

---

## 2. Feature overview

Two separate additions to the merchant profile:

**Bio** — short Instagram-style text (max 250 chars, max 5 lines) plus one
optional link. Lives on the profile object; there are no dedicated bio
endpoints, you just send the fields to `PUT /profile`.

**Intro video** — one short video per merchant with full CRUD. Has its own
endpoints, its own upload lifecycle, and its own visibility rules.

The two are independent. A merchant can have a bio and no video, or the reverse.

> `bio` is **not** `business_description`. `business_description` is the long
> "About this business" text and is unchanged. Show them as two separate fields.

---

## 3. Bio API

### 3.1 Read — `GET /api/merchants/profile`

Auth: merchant. This is the existing profile endpoint; the bio fields, the
intro video and a `limits` object were **added** to it. Everything that was
there before is unchanged.

```jsonc
{
  "profile": {
    "business_name": "Brass Works",
    "business_description": "Long-form about text…",
    // …all pre-existing fields…

    "username": "brassworks_1234",
    "profile_img": "https://cdn…/profile.jpg",

    "bio": "Handmade brass décor from Moradabad ✨\nShips worldwide.",
    "bio_link": "https://example.com",
    "bio_link_label": "Our catalogue",

    "intro_video": { /* owner view — see §4.1 — or null */ }
  },
  "limits": {
    "bio_max_chars": 250,
    "bio_max_lines": 5,
    "bio_link_label_max_chars": 60,
    "intro_video": {
      "max_size_bytes": 52428800,
      "max_size_mb": 50,
      "max_duration_seconds": 60,
      "allowed_extensions": ["mov", "mp4"],
      "max_title_chars": 120,
      "max_caption_chars": 500
    }
  }
}
```

**Drive your validation from `limits`, not from hardcoded numbers.** If the
server limits change, a hardcoded client silently disagrees with the server and
users get errors your UI said wouldn't happen.

### 3.2 Write — `PUT /api/merchants/profile`

Auth: merchant. `Content-Type: application/json`.

```jsonc
{
  "bio": "Handmade brass décor from Moradabad ✨\nShips worldwide.",
  "bio_link": "example.com",
  "bio_link_label": "Our catalogue"
}
```

**200**

```jsonc
{
  "message": "Profile updated successfully",
  "profile": {
    "business_name": "Brass Works",
    "business_email": "hello@example.com",
    "country_code": "IN",
    "verification_status": "approved",
    "bio": "Handmade brass décor from Moradabad ✨\nShips worldwide.",
    "bio_link": "https://example.com",
    "bio_link_label": "Our catalogue"
  }
}
```

Note `example.com` came back as `https://example.com` — the server normalises a
missing scheme. **Use the returned values to update your state**, do not assume
what you sent is what was stored.

**400**

```jsonc
{
  "error": "Validation error",
  "details": { "bio": ["Bio must be 250 characters or fewer (got 312)."] }
}
```

### 3.3 Field rules

| Field | Type | Limit | Notes |
|---|---|---|---|
| `bio` | string \| null | 250 chars, 5 lines | Emoji allowed and count as **1 character each**. Newlines preserved. |
| `bio_link` | string \| null | 512 chars | `http`/`https` only. A bare `example.com` is normalised to `https://`. |
| `bio_link_label` | string \| null | 60 chars | Ignored and cleared if there is no `bio_link`. |

**Update semantics — this trips people up:**

| You send | Result |
|---|---|
| key omitted | field unchanged |
| `"bio": "text"` | field set |
| `"bio": ""` | field **cleared** (returns `null`) |
| `"bio": null` | field **cleared** |

So a "clear my bio" button sends `{"bio": ""}`, and a form that only edits the
link must **not** send `bio` at all.

**Server-side sanitisation.** The stored value may differ from what you sent:

- HTML tags are stripped (`<b>hi</b>` → `hi`)
- `\r\n` and `\r` become `\n`
- 3+ consecutive blank lines collapse to 2
- zero-width and RTL-override characters are removed
- leading/trailing whitespace trimmed

Because length is checked **after** sanitisation, a 260-character string with
tags may pass. Your live character counter will occasionally disagree with the
server by a few characters — that is expected; trust the server's response.

**Rendering the bio:** it is plain text. Render with preserved line breaks
(`white-space: pre-line` on web, normal multi-line `Text` on mobile). **Never
render it as HTML** — no `dangerouslySetInnerHTML`, no `WebView`.

`@mentions` and `#hashtags` are stored as literal text and are **not**
linkified. Do not linkify them client-side either.

For `bio_link` on web, always use `target="_blank" rel="noopener noreferrer nofollow"`.

---

## 4. Intro video API

### 4.1 The video object

**Public shape** (what shoppers get):

```jsonc
{
  "id": 12,
  "title": "Meet the maker",
  "caption": "A 40-second hello from our workshop.",
  "video_url": "https://cdn…/merchant-intro-videos/8/12-9f3a….mp4",
  "thumbnail_url": "https://cdn…/12-9f3a…_thumb.jpg",
  "duration_seconds": 42,
  "resolution": "1080x1920"
}
```

**Owner shape** adds the fields the merchant needs to manage it:

```jsonc
{
  // …everything above, plus:
  "file_size_bytes": 18234221,
  "video_format": "mp4",
  "mime_type": "video/mp4",
  "duration_verified": true,
  "status": "ready",              // processing | ready | failed
  "failure_reason": null,
  "moderation_status": "approved", // pending | approved | rejected
  "moderation_notes": null,
  "is_active": true,
  "created_at": "2026-08-05T10:00:00",
  "updated_at": "2026-08-05T10:00:00"
}
```

`status`, `moderation_*`, `failure_reason` and `is_active` **never appear in a
public response**. If you are building a shopper-facing screen and want to
branch on them, you are using the wrong endpoint.

Two fields need care:

- **`thumbnail_url` can be `null`.** Thumbnail generation needs `ffmpeg`, which
  is not guaranteed to be installed. Always have a fallback (see §9).
- **`duration_verified: false`** means `duration_seconds` is a number the client
  reported, not one the server measured. Display it as approximate or not at all.

### 4.2 `GET /api/merchants/profile/intro-video`

Auth: merchant. Returns the owner view.

```jsonc
{
  "intro_video": { /* owner shape */ } | null,
  "limits": {
    "max_size_bytes": 52428800,
    "max_size_mb": 50,
    "max_duration_seconds": 60,
    "allowed_extensions": ["mov", "mp4"],
    "max_title_chars": 120,
    "max_caption_chars": 500
  }
}
```

**"No video" is `200` with `intro_video: null` — never a 404.** Do not treat the
empty state as an error.

| Code | Meaning |
|---|---|
| 200 | OK (video or `null`) |
| 401 / 403 | not authenticated / not a merchant |
| 404 | merchant profile not found |

### 4.3 `POST /api/merchants/profile/intro-video` — create

Auth: merchant. `multipart/form-data`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `video` | file | yes | MP4 or MOV, ≤ 50 MB, ≤ 60 s |
| `title` | string | no | ≤ 120 chars |
| `caption` | string | no | ≤ 500 chars |
| `duration_seconds` | integer | no | Your measured duration. Used only if the server cannot measure it itself — send it. |

**201**

```jsonc
{ "message": "Intro video uploaded successfully", "intro_video": { /* owner shape */ } }
```

| Code | Meaning | What the UI should do |
|---|---|---|
| 400 | invalid file or metadata | show `error`; do not retry unchanged |
| 401 / 403 | auth | re-auth |
| 404 | no merchant profile | send them to profile setup |
| **409** | a video already exists | offer **Replace** (§4.5), not another create |
| 413 | body exceeded the server request cap | same as 400 — file too big |
| 429 | 10 uploads in 24h | tell them to try tomorrow |
| 500 | storage failure | offer retry; **nothing was saved** |

### 4.4 `PUT /api/merchants/profile/intro-video` — update metadata

Auth: merchant. `application/json`. **Never touches the file.**

```jsonc
{ "title": "Meet the maker", "caption": "A 40-second hello", "is_active": true }
```

All three fields are optional; omitted keys are unchanged. `is_active: false`
hides the video from shoppers while keeping it — that is your show/hide toggle.

**200** → `{ "message": "Intro video updated successfully", "intro_video": {…} }`
· **400** validation · **404** no video exists

### 4.5 `PUT /api/merchants/profile/intro-video/file` — replace the file

Auth: merchant. `multipart/form-data`, same fields as create. `POST` is also
accepted for clients that cannot send multipart over `PUT`.

`title` and `caption` are **preserved** unless you send new ones. Moderation
state resets, because a new file is new content.

The new file is uploaded before the old one is deleted, so a failed replace
leaves the current video intact.

**200** → `{ "message": "Intro video replaced successfully", "intro_video": {…} }`
· **400** · **404** nothing to replace · **429** · **500**

### 4.6 `DELETE /api/merchants/profile/intro-video`

Auth: merchant.

**200** → `{ "message": "Intro video deleted successfully" }` · **404** nothing to delete

Deleting frees the slot — the merchant can immediately upload a new one. (Each
upload still counts toward the daily cap, so upload/delete loops are limited.)

---

## 5. Public (shopper-facing) API

No auth required.

### 5.1 `GET /api/merchants/{merchant_id}/public-profile`

Existing endpoint; now also returns `username`, `profile_img`, `bio`,
`bio_link`, `bio_link_label` and `intro_video` (public shape or `null`).

**404** when the merchant is soft-closed, past their deletion grace period, or
suspended.

### 5.2 `GET /api/merchants/{merchant_id}/intro-video`

Standalone read for clients that only need the video.

```jsonc
{ "intro_video": { /* public shape */ } | null }
```

**Always `200`, never `404`** — even for a merchant ID that does not exist. A
hidden, rejected or missing video are deliberately indistinguishable, so that a
status code cannot be used to probe moderation state.

### 5.3 When a video is publicly visible

All of these must hold, or you get `null`:

| Level | Condition |
|---|---|
| Merchant | not soft-closed, grace period not elapsed, account active |
| Merchant | **verified** (`is_verified` and `verification_status == "approved"`) |
| Video | not deleted, `is_active`, `status == "ready"`, `moderation_status == "approved"` |

**The bio uses only the first rule** — it is visible for any active merchant,
verified or not. Only the video requires verification.

Practical consequence: an unverified merchant sees their own video in the
dashboard but shoppers do not. Say so in the UI, or you will get support
tickets. Suggested copy: *"Your video will appear on your public profile once
your account is verified."*

---

## 6. Error handling

All errors share one shape:

```jsonc
{ "error": "Human-readable message", "details": { /* optional */ } }
```

`details` is either a string or a `{ field: [messages] }` map. A reusable
flattener:

```ts
async function readError(res: Response, fallback: string): Promise<string> {
  const body = await res.json().catch(() => null);
  if (!body) return fallback;
  const base = body.error || body.message || fallback;
  if (!body.details) return base;
  if (typeof body.details === 'string') return `${base}: ${body.details}`;
  const parts = Object.values(body.details as Record<string, string[] | string>)
    .flatMap(v => (Array.isArray(v) ? v : [v]));
  return parts.length ? parts.join(' ') : base;
}
```

> **Always guard `res.json()` with `.catch()`.** A proxy or gateway timeout can
> return HTML, and an unguarded parse throws a confusing `SyntaxError` instead
> of your error message.

---

## 7. UI state machine for the intro video

Branch on the owner-view fields in this order. Getting the order wrong shows
merchants the wrong message.

| Condition | State | Show |
|---|---|---|
| `intro_video === null` | **Empty** | Upload dropzone |
| `status === "processing"` | **Processing** | Spinner, no player (`video_url` may be `null`) |
| `status === "failed"` | **Failed** | Error + `failure_reason`; offer re-upload |
| `moderation_status === "pending"` | **In review** | Player + "awaiting review, not yet public" |
| `moderation_status === "rejected"` | **Rejected** | Error + `moderation_notes`; offer replace |
| `is_active === false` | **Hidden** | Player + "hidden from shoppers" + Show button |
| otherwise | **Live** | Player + Edit / Replace / Hide / Delete |

Actions available in every non-empty state: **Replace file**, **Edit title &
caption**, **Show/Hide**, **Delete**.

> `moderation_status` is `"approved"` on upload today — moderation is off by
> default. **Implement the pending and rejected states anyway.** They can be
> switched on server-side with a config flag and no client release, and a client
> that ignores them will show a "live" video that shoppers cannot see.

---

## 8. Integration recipes

### 8.1 Upload with a progress bar (web)

`fetch` cannot report upload progress. A 50 MB upload with no progress bar looks
like a hung page, so use `XMLHttpRequest`:

```ts
function uploadIntroVideo(
  file: File,
  opts: { title?: string; caption?: string; durationSeconds?: number | null;
          onProgress?: (pct: number) => void; replace?: boolean }
): Promise<IntroVideo> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append('video', file);
    if (opts.title !== undefined) form.append('title', opts.title);
    if (opts.caption !== undefined) form.append('caption', opts.caption);
    if (opts.durationSeconds != null) {
      form.append('duration_seconds', String(Math.round(opts.durationSeconds)));
    }

    const url = `${API_BASE_URL}/api/merchants/profile/intro-video${opts.replace ? '/file' : ''}`;
    const xhr = new XMLHttpRequest();
    xhr.open(opts.replace ? 'PUT' : 'POST', url);
    xhr.setRequestHeader('Authorization', `Bearer ${localStorage.getItem('access_token')}`);
    // Do NOT set Content-Type — the browser adds the multipart boundary.

    xhr.upload.onprogress = e => {
      if (e.lengthComputable) opts.onProgress?.(Math.round((e.loaded / e.total) * 100));
    };

    xhr.onload = () => {
      let body: any = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* non-JSON error page */ }
      if (xhr.status >= 200 && xhr.status < 300) return resolve(body?.intro_video);
      reject(new Error(body?.error || 'Upload failed'));
    };
    xhr.onerror = () => reject(new Error('Network error while uploading.'));
    xhr.send(form);
  });
}
```

### 8.2 Client-side validation before upload

Validate before sending, so the merchant is not made to wait out a 50 MB upload
just to be told the video is too long.

```ts
function readVideoMetadata(file: File): Promise<{ duration: number | null }> {
  return new Promise(resolve => {
    const url = URL.createObjectURL(file);
    const video = document.createElement('video');
    video.preload = 'metadata';
    const done = (r: { duration: number | null }) => { URL.revokeObjectURL(url); resolve(r); };
    video.onloadedmetadata = () =>
      done({ duration: Number.isFinite(video.duration) ? video.duration : null });
    // Codec the browser cannot decode: resolve with null rather than rejecting —
    // the server only validates the container, so the upload may still succeed.
    video.onerror = () => done({ duration: null });
    video.src = url;
  });
}

async function validate(file: File, limits: IntroVideoLimits) {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
  if (!limits.allowed_extensions.includes(ext)) return 'Use an MP4 or MOV file.';
  if (file.size === 0) return 'That file is empty.';
  if (file.size > limits.max_size_bytes) return `Video must be under ${limits.max_size_mb}MB.`;

  const { duration } = await readVideoMetadata(file);
  if (duration != null && duration > limits.max_duration_seconds + 0.5) {
    return `Video must be ${limits.max_duration_seconds} seconds or shorter.`;
  }
  return null; // pass duration to the upload as duration_seconds
}
```

### 8.3 Mobile upload (React Native)

```ts
const form = new FormData();
form.append('video', {
  uri: asset.uri,
  name: asset.fileName ?? 'intro.mp4',
  type: asset.type ?? 'video/mp4',
} as any);
if (title) form.append('title', title);
if (asset.duration) form.append('duration_seconds', String(Math.round(asset.duration)));

const res = await fetch(`${API_BASE_URL}/api/merchants/profile/intro-video`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}` }, // no Content-Type
  body: form,
});
```

For progress, use `react-native-blob-util` or `axios` with `onUploadProgress`.

### 8.4 Playing the video

```tsx
<video
  src={video.video_url}
  poster={video.thumbnail_url ?? undefined}  // may be null
  controls
  playsInline                                 // required, or iOS goes fullscreen
  preload="metadata"                          // do not pull 50MB on page load
/>
```

`preload="metadata"` matters: without it, every profile visit downloads the
whole file. With it, the browser fetches enough to show the first frame, which
also covers you when `thumbnail_url` is `null`.

### 8.5 Bio editor

```tsx
const max = limits.bio_max_chars ?? 250;
const over = bio.length > max;

<textarea value={bio} rows={4} onChange={e => setBio(e.target.value)} />
<span className={over ? 'text-red-600' : 'text-gray-500'}>{bio.length}/{max}</span>
<button disabled={over} onClick={save}>Save</button>
```

Count characters with `.length`, not bytes. An emoji is one character to the
merchant and one character to the server.

---

## 9. Gotchas — read this before you start

**Never send `business_phone` to `PUT /api/merchants/profile`.** The schema
rejects unknown keys, so one stray field 400s the *entire* request, including
your bio update. `business_email` is likewise not updatable here.

**Blank strings fail some validators.** `bank_account_number` requires 9–18
characters, so `""` is a validation error, not a clear. Omit those fields when
empty. This does **not** apply to `bio` — `""` correctly clears it.

**`thumbnail_url` can be `null`.** Thumbnails need `ffmpeg`, which is optional
in this deployment. Never bind an `<img src>` straight to it.

**`duration_seconds` may be unmeasured.** When `duration_verified` is `false`
the value came from a client. The 60-second limit is enforced in the browser
always and on the server only when `ffprobe` is available — **file size is the
limit that always holds.** Send `duration_seconds` on upload so the server has
something to store.

**409 means replace, not retry.** A merchant has exactly one video. On 409,
switch the UI to the replace flow rather than looping on create.

**Disable the submit button during upload.** Two concurrent creates race; the
server has a lock and one will lose with a 409, but the UX is bad.

**`null` is a normal state, not an error.** Both `intro_video: null` and
`bio: null` mean "not set". Never render an error for them.

**Public endpoints return `null`, not 404, for hidden videos.** Do not infer
"the merchant has a video but it is hidden" from a status code — you cannot, by
design.

**An unverified merchant's video is invisible to shoppers** even though the
merchant can see it in their dashboard. Tell them why.

**CDN URLs are immutable.** Every upload gets a fresh UUID key, so a replaced
video always has a new `video_url`. Cache-bust query strings are unnecessary —
just re-read the object from the API.

**Run `python init_db.py` before pointing a client at a freshly pulled backend.**
Without migration 010 the `merchant_intro_videos` table does not exist and
`GET /api/merchants/profile` returns 500 — the whole profile screen, not just
the video section.

---

## 10. Quick reference

| Method | Path | Auth | Body | Success |
|---|---|---|---|---|
| GET | `/api/merchants/profile` | merchant | — | 200 `{profile, limits}` |
| PUT | `/api/merchants/profile` | merchant | JSON bio fields | 200 `{message, profile}` |
| GET | `/api/merchants/profile/intro-video` | merchant | — | 200 `{intro_video, limits}` |
| POST | `/api/merchants/profile/intro-video` | merchant | multipart | 201 `{message, intro_video}` |
| PUT | `/api/merchants/profile/intro-video` | merchant | JSON metadata | 200 `{message, intro_video}` |
| PUT/POST | `/api/merchants/profile/intro-video/file` | merchant | multipart | 200 `{message, intro_video}` |
| DELETE | `/api/merchants/profile/intro-video` | merchant | — | 200 `{message}` |
| GET | `/api/merchants/{id}/intro-video` | **public** | — | 200 `{intro_video}` |
| GET | `/api/merchants/{id}/public-profile` | **public** | — | 200 profile + bio + video |

**Limits:** bio 250 chars / 5 lines · link 512 chars · label 60 chars · video
MP4 or MOV, 50 MB, 60 s · title 120 chars · caption 500 chars · 1 active video ·
10 uploads per merchant per day.

**Status codes:** 200/201 OK · 400 validation · 401 no auth · 403 not a merchant
· 404 not found · 409 video already exists · 413 body too large · 429 daily cap
· 500 server/storage.

### curl smoke test

```bash
TOKEN="<merchant access token>"
BASE="http://localhost:5110/api/merchants"

# Read profile (bio, video, limits)
curl -s "$BASE/profile" -H "Authorization: Bearer $TOKEN"

# Set the bio
curl -s -X PUT "$BASE/profile" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"bio":"Handmade brass decor.\nShips worldwide.","bio_link":"example.com","bio_link_label":"Catalogue"}'

# Upload the intro video
curl -s -X POST "$BASE/profile/intro-video" -H "Authorization: Bearer $TOKEN" \
  -F "video=@intro.mp4" -F "title=Meet the maker" -F "duration_seconds=42"

# Update metadata / hide
curl -s -X PUT "$BASE/profile/intro-video" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"is_active":false}'

# Replace the file
curl -s -X PUT "$BASE/profile/intro-video/file" -H "Authorization: Bearer $TOKEN" \
  -F "video=@new-intro.mp4"

# Delete
curl -s -X DELETE "$BASE/profile/intro-video" -H "Authorization: Bearer $TOKEN"

# Public reads (no auth)
curl -s "$BASE/1/intro-video"
curl -s "$BASE/1/public-profile"
```

### TypeScript types

```ts
export interface BioFields {
  bio: string | null;
  bio_link: string | null;
  bio_link_label: string | null;
}

export interface IntroVideo {
  id: number;
  title: string | null;
  caption: string | null;
  video_url: string | null;
  thumbnail_url: string | null;      // null when ffmpeg is unavailable
  duration_seconds: number | null;
  resolution: string | null;
  // Owner view only:
  file_size_bytes?: number | null;
  video_format?: string | null;
  mime_type?: string | null;
  duration_verified?: boolean;
  status?: 'processing' | 'ready' | 'failed';
  failure_reason?: string | null;
  moderation_status?: 'pending' | 'approved' | 'rejected';
  moderation_notes?: string | null;
  is_active?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface IntroVideoLimits {
  max_size_bytes: number;
  max_size_mb: number;
  max_duration_seconds: number;
  allowed_extensions: string[];
  max_title_chars: number;
  max_caption_chars: number;
}
```

A complete, working implementation of all of the above is in
`Ecommerce/src/services/merchantProfileApi.ts` — copy from it rather than
reimplementing.
