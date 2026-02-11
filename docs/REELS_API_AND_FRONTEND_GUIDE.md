# Reels API – Developer & Frontend Guide

This document describes the Reels APIs for **Postman/API developers** (methods, params, responses) and for **frontend developers** (what to use when, what each field means, and how reels work).

---

# Part 1: For API / Postman developers

Base URL: your backend host (e.g. `https://api.example.com`). All endpoints under `/api/reels` or `/api/reels/...`.

**Authentication:** Where "Auth: Bearer" is required, send header:  
`Authorization: Bearer <JWT_ACCESS_TOKEN>`.

**Content types:**  
- JSON: `Content-Type: application/json`  
- Upload: `Content-Type: multipart/form-data`

---

## 1. Upload a reel

**Method:** `POST`  
**Path:** `/api/reels`  
**Auth:** Bearer required (merchant only)  
**Content-Type:** `multipart/form-data`  
**Rate limit:** 10 uploads per hour per user.

**Two modes (use one, not both):**

| Mode    | Required form fields              | Optional form fields                          |
|---------|-----------------------------------|-----------------------------------------------|
| **AOIN**   | `video` (file), `description`, `product_id` (integer) | — |
| **External** | `video` (file), `description`, `product_url` (https), `product_name` | `platform`, `category_id`, `category_name` |

**Form fields:**

| Field          | Type   | Required | Description |
|----------------|--------|----------|-------------|
| video          | file   | Yes      | Video file. Allowed: MP4, WebM, MOV. Max 100MB, max 60s. |
| description    | string | Yes      | Reel description. Max 5000 characters. |
| product_id     | integer| For AOIN | Your approved product ID with stock > 0. Use only for AOIN reels. |
| product_url    | string | For external | Full product URL (must start with `https://`). Max 2048 chars. |
| product_name   | string | For external | Display name of the product. Max 500 chars. |
| platform       | string | No       | For external only. One of: `aoin`, `flipkart`, `amazon`, `myntra`, `other`. Default `other`. |
| category_id    | integer| No       | For external only. Must be an existing, active category ID. |
| category_name  | string | No       | For external only. Display category name. Max 255 chars. |

**Validation rules:**
- Send **either** AOIN (`product_id` only) **or** external (`product_url` + `product_name`). Sending both or neither returns `400`.
- External: `product_url` must be `https`; `platform` must be from the list above.

**Success response:** `201 Created`  
Body: `{ "status": "success", "message": "Reel uploaded successfully.", "data": <reel object> }`  
See “Reel object (response)” below for `data` shape.

**Error responses:**
- `400` – Validation (e.g. missing/invalid fields, both or neither AOIN/external).
- `403` – Not a merchant.
- `500` – Server or storage error.

---

## 2. Get a single reel

**Method:** `GET`  
**Path:** `/api/reels/<reel_id>`  
**Auth:** None.

**Query parameters:**

| Parameter   | Type    | Default | Description |
|------------|---------|---------|-------------|
| track_view | boolean | true    | If true, counts this request as a view. |
| view_duration | integer | —     | Optional. Watch time in seconds (for analytics). |

**Success response:** `200 OK`  
Body: `{ "status": "success", "data": <reel object> }`

**Error responses:** `404` – Reel not found.

---

## 3. Track reel view (without loading full reel)

**Method:** `POST`  
**Path:** `/api/reels/<reel_id>/view`  
**Auth:** Bearer required.  
**Content-Type:** `application/json`

**Body (optional):**
```json
{ "view_duration": 5 }
```
`view_duration`: integer, seconds watched.

**Success response:** `200 OK`  
**Error responses:** `401`, `404`, `500`.

---

## 4. Get public reel feed

**Method:** `GET`  
**Path:** `/api/reels/public`  
**Auth:** None.

**Query parameters:**

| Parameter  | Type   | Default | Description |
|-----------|--------|---------|-------------|
| page      | integer| 1       | Page number. |
| per_page  | integer| 20      | Items per page (max 100). |
| category_id | integer | —     | Filter by category (AOIN product category or external reel category). |
| merchant_id | integer | —     | Filter by merchant. |
| start_date | string | —      | ISO date/time (e.g. `2024-01-01T00:00:00Z`). |
| end_date   | string | —      | ISO date/time. |
| sort_by   | string | newest  | One of: `newest`, `likes`, `views`, `shares`. |

**Success response:** `200 OK`  
Body includes: `data` (array of reel objects), `pagination` (page, per_page, total, pages, etc.), and optionally `filters_applied`.

---

## 5. Get current merchant’s reels (my reels)

**Method:** `GET`  
**Path:** `/api/reels/merchant/my`  
**Auth:** Bearer required (merchant).

**Query parameters:**

| Parameter   | Type    | Default | Description |
|------------|---------|---------|-------------|
| page       | integer | 1       | Page number. |
| per_page   | integer | 20      | Items per page (max 100). |
| include_all| boolean | false   | If true, returns all reels (including non-visible). |
| category_id| integer | —       | Filter by category. |
| start_date | string  | —       | ISO date/time. |
| end_date   | string  | —       | ISO date/time. |
| sort_by    | string  | newest  | `newest`, `likes`, `views`, `shares`. |

**Success response:** `200 OK`  
Body: list of reel objects with pagination; may include `disabling_reasons` and `is_visible` when relevant.

**Error responses:** `403` – Not a merchant.

---

## 6. Get public reels by merchant

**Method:** `GET`  
**Path:** `/api/reels/merchant/<merchant_id>`  
**Auth:** None.

**Query parameters:** `page`, `per_page` (same as above).

**Success response:** `200 OK`  
**Error responses:** `404` – Merchant not found.

---

## 7. Get merchant reel stats (aggregate)

**Method:** `GET`  
**Path:** `/api/reels/merchant/<merchant_id>/stats`  
**Auth:** None.

**Success response:** `200 OK`  
Body: `{ "status": "success", "data": { "merchant_id", "total_reels", "total_likes", "total_views", "total_shares" } }`  
**Error responses:** `404`, `500`.

---

## 8. Get recently viewed reels

**Method:** `GET`  
**Path:** `/api/reels/recently-viewed`  
**Auth:** Bearer required.

**Query parameters:** `page`, `per_page`, `fields` (comma-separated field names).

**Success response:** `200 OK`  
Body: `data.reels` (array of reel objects), `data.pagination`.  
**Error responses:** `401`, `500`.

---

## 9. Update reel (description only)

**Method:** `PUT`  
**Path:** `/api/reels/<reel_id>`  
**Auth:** Bearer required (owner only).  
**Content-Type:** `application/json`

**Body:**
```json
{ "description": "New description text (max 5000 characters)" }
```

**Success response:** `200 OK`  
**Error responses:** `400` (invalid input), `403` (not owner), `404`.

---

## 10. Delete a reel

**Method:** `DELETE`  
**Path:** `/api/reels/<reel_id>`  
**Auth:** Bearer required (owner only).

**Success response:** `200 OK`  
**Error responses:** `403`, `404`.

---

## 11. Get available products (for AOIN reel upload)

**Method:** `GET`  
**Path:** `/api/reels/products/available`  
**Auth:** Bearer required (merchant).

Returns the list of the merchant’s products that are approved, active, and have stock > 0 (suitable for linking to an AOIN reel).

**Success response:** `200 OK`  
**Error responses:** `403` – Not a merchant.

---

## 12. Like a reel

**Method:** `POST`  
**Path:** `/api/reels/<reel_id>/like`  
**Auth:** Bearer required.

**Success response:** `200 OK`  
**Error responses:** `400` (e.g. already liked), `401`, `404`.

---

## 13. Unlike a reel

**Method:** `POST`  
**Path:** `/api/reels/<reel_id>/unlike`  
**Auth:** Bearer required.

**Success response:** `200 OK`  
**Error responses:** `400` (e.g. not liked), `401`, `404`.

---

## 14. Share a reel (increment share count)

**Method:** `POST`  
**Path:** `/api/reels/<reel_id>/share`  
**Auth:** None.

**Success response:** `200 OK`  
**Error responses:** `404`.

---

## 15. Search reels

**Method:** `GET`  
**Path:** `/api/reels/search`  
**Auth:** None.

**Query parameters:**

| Parameter   | Type   | Required | Description |
|------------|--------|----------|-------------|
| q          | string | Yes      | Search text (description, product name, merchant name). |
| page       | integer| No       | Default 1. |
| per_page   | integer| No       | Default 20, max 100. |
| category_id| integer| No       | Filter by category. |
| merchant_id| integer| No       | Filter by merchant. |
| start_date | string | No       | ISO date/time. |
| end_date   | string | No       | ISO date/time. |

**Success response:** `200 OK`  
Body: search results as reel objects with pagination.  
**Error responses:** `400` (e.g. missing `q`), `500`.

---

## 16. Batch delete reels

**Method:** `POST`  
**Path:** `/api/reels/batch/delete`  
**Auth:** Bearer required (merchant).  
**Content-Type:** `application/json`  
**Rate limit:** 5 batch operations per hour.

**Body:**
```json
{ "reel_ids": [1, 2, 3] }
```
Max 50 IDs per request.

**Success response:** `200 OK`  
**Error responses:** `400`, `403`, `500`.

---

## 17. User reel stats

**Method:** `GET`  
**Path:** `/api/reels/user/stats`  
**Auth:** Bearer required.

**Success response:** `200 OK`  
Body: user’s reel interaction statistics.  
**Error responses:** `401`, `500`.

---

## 18. Merchant reel analytics

**Method:** `GET`  
**Path:** `/api/reels/merchant/my/analytics`  
**Auth:** Bearer required (merchant).

**Query parameters:** `page`, `per_page`, `start_date`, `end_date`, `sort_by` (e.g. `created_at`, `views`, `likes`, `shares`, `engagement`).

**Success response:** `200 OK`  
**Error responses:** `401`, `403`, `500`.

---

## 19. Get user’s shared reels

**Method:** `GET`  
**Path:** `/api/reels/user/shared`  
**Auth:** Bearer required.

**Query parameters:** `page`, `per_page`.

**Success response:** `200 OK`  
Body: reels the user has shared, with `shared_at` where applicable.  
**Error responses:** `401`, `500`.

---

## Reel object (response shape)

Every reel in list/detail responses includes the following. **AOIN vs external** changes only how product info is represented.

**Common fields (all reels):**

| Field            | Type    | Description |
|------------------|---------|-------------|
| reel_id          | integer | Unique reel ID. |
| merchant_id      | integer | Owner merchant ID. |
| product_id       | integer or null | Set for AOIN reels; `null` for external. |
| product_url      | string or null | Link to product: for AOIN it’s generated (app product page); for external it’s what was sent. |
| platform         | string or null | `aoin` \| `flipkart` \| `amazon` \| `myntra` \| `other`. |
| video_url        | string  | Playable video URL. |
| thumbnail_url    | string or null | Thumbnail image URL. |
| description      | string  | Reel description. |
| duration_seconds | integer or null | Video length in seconds. |
| views_count      | integer | View count. |
| likes_count      | integer | Like count. |
| shares_count     | integer | Share count. |
| is_active        | boolean | Whether reel is active. |
| approval_status  | string  | e.g. `approved`. |
| created_at       | string  | ISO 8601 datetime. |
| updated_at       | string  | ISO 8601 datetime. |

**When requested (e.g. feed, detail):**

- **disabling_reasons** – Array of reason codes if the reel is not visible (e.g. `REEL_INACTIVE`, `PRODUCT_OUT_OF_STOCK`). Omitted or empty when not requested.
- **is_visible** – Boolean; `true` if the reel is eligible to show in public feed.
- **product** – Present **only for AOIN reels** (`product_id` not null). Object: `product_id`, `product_name`, `category_id`, `category_name`, `stock_qty`, `selling_price`.
- **product_name** – Present **only for external reels** (no `product` object). Display name of the product.
- **category_id** – For external reels, category ID (if set).
- **category_name** – For external reels, category display name (if set).
- **merchant** – When requested: `merchant_id`, `business_name`, `profile_img`.

**How to tell AOIN vs external in response:**  
If `product_id` is a number and `product` exists → AOIN reel (use `product` and `product_url`).  
If `product_id` is `null` → external reel (use `product_url`, `product_name`, `platform`, and optionally `category_id` / `category_name`).

---

# Part 2: For frontend developers

## What are reels?

Reels are short videos (e.g. up to 60 seconds) that merchants upload. Each reel is linked to **one product**:

- **AOIN product:** The product lives in your app (your catalog). The backend generates the product page URL.
- **External product:** The product is on another site (e.g. Flipkart, Amazon). The merchant sends the product URL and name; you open that URL when the user taps “View product”.

The same feed shows both types. Your UI can show a single “View product” button and use `product_url` for the link; optionally use `platform` for a badge or icon (e.g. “Flipkart”, “Amazon”).

---

## When to use which API

- **Feed (home/discover):** `GET /api/reels/public` with `page`, `per_page`, optional `category_id`, `sort_by`. No auth.
- **Single reel (detail / player):** `GET /api/reels/<reel_id>`. Use `track_view=false` only if you don’t want to count this as a view.
- **Track view without loading reel:** `POST /api/reels/<reel_id>/view` with optional `view_duration` (e.g. when user leaves after 5 seconds).
- **Upload (merchant):** `POST /api/reels` with `multipart/form-data`. Choose **either** AOIN (send `product_id`) **or** external (send `product_url` + `product_name`). Never send both; never omit both.
- **My reels (merchant):** `GET /api/reels/merchant/my`. Use `include_all=true` only in “manage reels” to see non-visible ones.
- **Public reels by merchant (profile):** `GET /api/reels/merchant/<merchant_id>`.
- **Search:** `GET /api/reels/search?q=<text>` with optional `category_id`, `merchant_id`, dates.
- **Like / unlike:** `POST /api/reels/<reel_id>/like`, `POST /api/reels/<reel_id>/unlike` (auth required).
- **Share:** `POST /api/reels/<reel_id>/share` (increments share count; no auth).
- **Edit description:** `PUT /api/reels/<reel_id>` with `{ "description": "..." }`.
- **Delete:** `DELETE /api/reels/<reel_id>`.
- **Available products for AOIN upload:** `GET /api/reels/products/available` (merchant only) to show a product picker for AOIN reels.

---

## Upload flow (frontend)

1. **Choose type:** “Link to my product” (AOIN) vs “Link to external product” (external).
2. **AOIN:**  
   - Call `GET /api/reels/products/available` to get the list.  
   - User picks a product → you send `product_id` with `video` and `description`.  
   - Do **not** send `product_url` or `product_name`.
3. **External:**  
   - User enters product URL (must be `https`) and product name.  
   - Optionally: platform (dropdown: Flipkart, Amazon, Myntra, Other), category (from your categories API), category name.  
   - Send `product_url`, `product_name`, `video`, `description`.  
   - Do **not** send `product_id`.
4. **Common:** Always send `video` (file) and `description`. Use `multipart/form-data`.
5. **Errors:**  
   - “Provide either product_id (AOIN) or product_url and product_name (external)” → user must pick one type and fill the right fields.  
   - “Provide either ... not both” → remove either `product_id` or the external fields.

---

## Displaying a reel in the feed

- **Video:** Use `video_url` for the player and `thumbnail_url` for the poster/placeholder.
- **Product link:** Use `product_url` for the “View product” (or “Buy”) button. It works for both AOIN and external reels.
- **Product name:**  
  - AOIN: use `product.product_name`.  
  - External: use top-level `product_name`.
- **Category / platform:**  
  - AOIN: you can use `product.category_name` if present.  
  - External: use `category_name` and/or `platform` for a badge (e.g. “Flipkart”).
- **Merchant:** If you need shop name or avatar, use the `merchant` object when the API includes it (`business_name`, `profile_img`).
- **Visibility:** If you’re showing “my reels” and the API returns `disabling_reasons` or `is_visible: false`, you can show a message (e.g. “Hidden because product is out of stock”) using the reason codes.

---

## Pagination

List endpoints return a `pagination` object (or similar) with at least:

- `page` or `current_page`
- `per_page`
- `total`
- `pages`
- Often `has_next`, `has_prev`

Use these to build “Load more” or page numbers. Typical `per_page` is 20; max is 100.

---

## Errors

Responses use a common shape:

- **Body:** `{ "error": "<user-facing message>", "code": "<ERROR_CODE>", "details": { ... } }`
- **Status:** 400 (validation), 401 (unauthorized), 403 (forbidden), 404 (not found), 500 (server error).

Show `error` to the user; use `code` and `details` for logging or specific UI (e.g. highlight the field in `details.field`).

---

## Summary table: fields you care about

| Purpose           | Where it comes from (AOIN)        | Where it comes from (External)   |
|------------------|-----------------------------------|----------------------------------|
| Open product     | `product_url`                     | `product_url`                    |
| Product name     | `product.product_name`            | `product_name`                   |
| Price / stock    | `product.selling_price`, `product.stock_qty` | Not provided (external link) |
| Category         | `product.category_name`           | `category_name`                  |
| Platform badge   | “AOIN” or hide                    | `platform` (flipkart, amazon, …) |

Use this single doc for both Postman/API testing and frontend implementation.
