# Reels "Not Interested" API Documentation

## Overview

The **Not Interested** feature lets an authenticated user personalize their reel
feeds by hiding content they don't want to see:

- **Not interested in this vendor** — hides *all* reels from a specific merchant.
- **Not interested in this category** — hides *all* reels in a specific category.

These are **per-user preferences only**. They affect only the requesting user's
reel feeds (recommended / trending / following / public). They do **not**:

- affect any other user's feeds,
- hide the vendor's products from product listings, search, or category pages,
- block ordering from that vendor.

Both signals are fully reversible (the user can undo them), and the API exposes a
list endpoint so you can build a "Manage not interested" settings screen.

> **Note on blocking a followed vendor:** if the user is currently following a
> vendor and then marks that vendor as "not interested", the backend
> automatically unfollows them (the two states are contradictory). The response
> reports this via `auto_unfollowed`.

---

## Authentication

All endpoints require a JWT Bearer token:

```
Authorization: Bearer <your_jwt_token>
```

The only exception in behavior (not in auth) is that the **feeds themselves**
apply these filters automatically once the user is authenticated — see
[How filtering affects feeds](#how-filtering-affects-the-feeds) below.

---

## Endpoints summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/reels/not-interested/merchant/{merchant_id}` | Mark a vendor as not interested |
| `DELETE` | `/api/reels/not-interested/merchant/{merchant_id}` | Undo vendor "not interested" |
| `POST` | `/api/reels/not-interested/category/{category_id}` | Mark a category as not interested |
| `DELETE` | `/api/reels/not-interested/category/{category_id}` | Undo category "not interested" |
| `GET` | `/api/reels/not-interested` | List the user's blocked vendors + hidden categories |

---

## 1. Mark a vendor as "not interested"

Hides every reel from this merchant in the current user's feeds.

**Endpoint:** `POST /api/reels/not-interested/merchant/{merchant_id}`

### Path parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `merchant_id` | integer | Yes | The merchant (vendor) ID to hide |

### Request body

None.

### Success response — `201 Created`

```json
{
  "status": "success",
  "message": "Vendor marked as not interested. Their reels are hidden from your feeds.",
  "data": {
    "merchant_id": 42,
    "business_name": "Acme Store",
    "auto_unfollowed": true
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `auto_unfollowed` | boolean | `true` if the user was following this vendor and has now been unfollowed |

### Already marked — `200 OK`

Calling it again is idempotent (no error):

```json
{
  "status": "success",
  "message": "Vendor already marked as not interested",
  "data": { "merchant_id": 42 }
}
```

### Error responses

| Status | Body | When |
|--------|------|------|
| `401 Unauthorized` | — | Missing/invalid JWT |
| `404 Not Found` | `{ "error": "Merchant not found" }` | `merchant_id` doesn't exist |
| `404 Not Found` | `{ "error": "User not found" }` | Token identity invalid |
| `500` | `{ "error": "Failed to mark vendor as not interested: ..." }` | Server error |

---

## 2. Undo vendor "not interested"

Restores the vendor's reels to the user's feeds. (Does **not** re-follow them.)

**Endpoint:** `DELETE /api/reels/not-interested/merchant/{merchant_id}`

### Success response — `200 OK`

```json
{
  "status": "success",
  "message": "Vendor restored to your feeds",
  "data": { "merchant_id": 42 }
}
```

### Error responses

| Status | Body | When |
|--------|------|------|
| `400 Bad Request` | `{ "error": "This vendor is not in your not-interested list", "data": { "merchant_id": 42 } }` | Vendor wasn't blocked |
| `401 Unauthorized` | — | Missing/invalid JWT |
| `500` | `{ "error": "Failed to restore vendor: ..." }` | Server error |

---

## 3. Mark a category as "not interested"

Hides every reel in this category in the current user's feeds. Covers both AOIN
reels (category derived from the linked product) and external reels (category
stored on the reel).

**Endpoint:** `POST /api/reels/not-interested/category/{category_id}`

### Path parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category_id` | integer | Yes | The category ID to hide |

### Success response — `201 Created`

```json
{
  "status": "success",
  "message": "Category marked as not interested. Its reels are hidden from your feeds.",
  "data": {
    "category_id": 7,
    "category_name": "Electronics"
  }
}
```

### Already marked — `200 OK`

```json
{
  "status": "success",
  "message": "Category already marked as not interested",
  "data": { "category_id": 7 }
}
```

### Error responses

| Status | Body | When |
|--------|------|------|
| `401 Unauthorized` | — | Missing/invalid JWT |
| `404 Not Found` | `{ "error": "Category not found" }` | `category_id` doesn't exist |
| `500` | `{ "error": "Failed to mark category as not interested: ..." }` | Server error |

---

## 4. Undo category "not interested"

**Endpoint:** `DELETE /api/reels/not-interested/category/{category_id}`

### Success response — `200 OK`

```json
{
  "status": "success",
  "message": "Category restored to your feeds",
  "data": { "category_id": 7 }
}
```

### Error responses

| Status | Body | When |
|--------|------|------|
| `400 Bad Request` | `{ "error": "This category is not in your not-interested list", "data": { "category_id": 7 } }` | Category wasn't hidden |
| `401 Unauthorized` | — | Missing/invalid JWT |
| `500` | `{ "error": "Failed to restore category: ..." }` | Server error |

---

## 5. List "not interested" preferences

Returns everything the user has marked as not interested — use this to build a
settings / management screen.

**Endpoint:** `GET /api/reels/not-interested`

### Success response — `200 OK`

```json
{
  "status": "success",
  "data": {
    "blocked_merchants": [
      {
        "merchant_id": 42,
        "business_name": "Acme Store",
        "profile_img": "https://res.cloudinary.com/.../acme.jpg",
        "created_at": "2026-06-01T10:15:30.123456+00:00"
      }
    ],
    "hidden_categories": [
      {
        "category_id": 7,
        "category_name": "Electronics",
        "created_at": "2026-06-01T10:16:05.987654+00:00"
      }
    ]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `blocked_merchants[]` | array | Vendors hidden by this user, newest first |
| `hidden_categories[]` | array | Categories hidden by this user, newest first |
| `created_at` | ISO 8601 string | When the preference was set (UTC) |

`profile_img` / `business_name` / `category_name` may be `null` if the underlying
record was removed.

---

## How filtering affects the feeds

Once a user has marked vendors/categories as "not interested", these reel
endpoints automatically exclude the hidden content **for that authenticated user**:

| Endpoint | Behavior |
|----------|----------|
| `GET /api/reels/feed/recommended` | Filters applied (auth required) |
| `GET /api/reels/feed/following` | Filters applied (auth required) |
| `GET /api/reels/feed/trending` | Filters applied **when authenticated**; anonymous callers get the unfiltered feed |
| `GET /api/reels/public` | Filters applied **when authenticated**; anonymous callers get the unfiltered feed |

No extra query parameters are needed — the backend resolves the user from the JWT
and applies their preferences server-side. Anonymous (no-token) requests are never
filtered.

> **Caching:** recommended/following feeds may be cached briefly. The backend
> invalidates the user's feed cache whenever they change a "not interested"
> preference, so the next feed fetch reflects the change immediately.

---

## Frontend integration tips

### Where to get the IDs

- `merchant_id` and `category_id` are already present on each reel object returned
  by the feed endpoints (`merchant.merchant_id`, and `category_id` /
  `product.category_id`). So a "Not interested" action on a reel card can call the
  relevant endpoint directly without an extra lookup.

### Suggested UX flow for a reel card "⋯ → Not interested" menu

```
Not interested in this reel
 ├── Hide reels from "Acme Store"      → POST /api/reels/not-interested/merchant/42
 └── Hide reels in "Electronics"       → POST /api/reels/not-interested/category/7
```

After a successful `POST`, remove the affected reels from the in-memory list
locally for an instant response, then let the next feed fetch confirm.

### Example calls

```js
// Mark vendor as not interested
await fetch(`/api/reels/not-interested/merchant/${merchantId}`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}` },
});

// Mark category as not interested
await fetch(`/api/reels/not-interested/category/${categoryId}`, {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}` },
});

// Settings screen: load current preferences
const res = await fetch('/api/reels/not-interested', {
  headers: { Authorization: `Bearer ${token}` },
});
const { data } = await res.json();
// data.blocked_merchants, data.hidden_categories

// Undo from settings screen
await fetch(`/api/reels/not-interested/merchant/${merchantId}`, {
  method: 'DELETE',
  headers: { Authorization: `Bearer ${token}` },
});
```

### Idempotency

- `POST` is safe to call repeatedly — a second call returns `200` with an
  "already marked" message instead of an error.
- `DELETE` on something not in the list returns `400` — treat this as "already
  removed" if you don't want to surface it as an error.

---

## CORS

All endpoints support `OPTIONS` preflight and the standard CORS headers used
across the API (`Authorization`, `Content-Type`, etc.).
