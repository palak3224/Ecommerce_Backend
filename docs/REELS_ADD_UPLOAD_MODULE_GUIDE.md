# Add Reels – Module Guide

This document is the **module guide for adding/uploading reels** only. It is for **Postman/API developers** (API contract, fields, validation) and **frontend developers** (how the add-reel flow works and what each field is for). No frontend code—explanations only.

---

# Part 1: For API / Postman developers

## Upload reel

**Method:** `POST`  
**Path:** `/api/reels`  
**Auth:** Bearer required (merchant only).  
**Header:** `Authorization: Bearer <JWT_ACCESS_TOKEN>`  
**Content-Type:** `multipart/form-data`  
**Rate limit:** 10 uploads per hour per user.

---

### Two modes (use one, not both)

The API supports two ways to link a reel to a product. You must choose one.

| Mode | When to use | What you send |
|------|-------------|----------------|
| **AOIN** | Product is from your app’s catalog (your product ID). | `video`, `description`, `product_id`. Do **not** send `product_url` or `product_name`. |
| **External** | Product is on another site (e.g. Flipkart, Amazon). | `video`, `description`, `product_url`, `product_name`. Do **not** send `product_id`. Optionally `platform`, `category_id`, `category_name`. |

Sending both modes (e.g. `product_id` and `product_url` + `product_name`) or neither returns **400** with a validation error.

---

### Form fields (multipart/form-data)

**Required for every upload**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| video | file | Yes | Video file. Allowed: **MP4, WebM, MOV**. Max size **100MB**, max duration **60 seconds**. |
| description | string | Yes | Reel description. Max **5000** characters. |

**For AOIN reels only**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| product_id | integer | Yes (for AOIN) | Your product ID. Product must be **approved**, **active**, and have **stock > 0**. Only **parent** products (not variants). |

**For external reels only**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| product_url | string | Yes (for external) | Full URL of the product page. Must start with **https://**. Max **2048** characters. |
| product_name | string | Yes (for external) | Display name of the product. Max **500** characters. |
| platform | string | No | One of: **aoin**, **flipkart**, **amazon**, **myntra**, **other**. Default **other**. Max 50 characters. |
| category_id | integer | No | Your app’s category ID (must exist and be active). Used for filtering and display. |
| category_name | string | No | Display name for the category. Max **255** characters. |

---

### Validation rules

- **Mode:** Either (a) only `product_id` (AOIN) or (b) both `product_url` and `product_name` (external). Not both, not neither.
- **AOIN:** `product_id` must be an integer; product must belong to the merchant and be approved, active, in stock, and a parent product.
- **External:** `product_url` must be **https** and within length; `platform` if sent must be from the allowlist; `category_id` if sent must exist and be active; string lengths as above.

---

### Success response

**Status:** `201 Created`

**Body:**
```json
{
  "status": "success",
  "message": "Reel uploaded successfully.",
  "data": { ... }
}
```

`data` is the created reel object. Relevant fields for add-reel:

| Field | Type | Description |
|-------|------|-------------|
| reel_id | integer | New reel ID. |
| merchant_id | integer | Owner merchant. |
| product_id | integer or null | Set for AOIN; null for external. |
| product_url | string or null | For AOIN: generated app product page URL. For external: the URL you sent. |
| platform | string or null | aoin \| flipkart \| amazon \| myntra \| other. |
| video_url | string | Playable video URL. |
| thumbnail_url | string or null | Thumbnail image URL. |
| description | string | Reel description. |
| views_count, likes_count, shares_count | integer | Counts (initially 0). |
| is_active | boolean | true. |
| created_at, updated_at | string | ISO 8601. |
| product | object | **Only for AOIN.** Contains product_id, product_name, category_id, category_name, stock_qty, selling_price. |
| product_name | string | **Only for external.** The name you sent. |
| category_id, category_name | mixed | **Only for external.** If you sent them. |
| merchant | object | When included: merchant_id, business_name, profile_img. |

---

### Error responses

| Status | Meaning |
|--------|--------|
| 400 | Validation: missing/invalid fields, wrong mode (both or neither AOIN/external), invalid URL/platform/category, or file (type/size). Response body: `{ "error": "<message>", "code": "<ERROR_CODE>", "details": { ... } }`. |
| 403 | User is not a merchant. |
| 500 | Server or storage error. |

---

# Part 2: For frontend developers

## What this module does

The **Add Reels** flow lets a merchant upload a short video (reel) and link it to **one product**. The product can be:

- **From your app (AOIN):** A product from the merchant’s own catalog in your app. The backend knows the product and will generate the product page link.
- **From elsewhere (external):** A product on another site (e.g. Flipkart, Amazon, Myntra). The merchant provides the product page URL and name; your app only stores and displays that link.

The same feed shows both types. For the user, there is a single “View product” action; you use the `product_url` returned by the API for that link.

---

## When to use which mode

- **AOIN:** The merchant chooses “Link to my product” (or similar) and picks one of their **approved, in-stock** products from your app. You need to call **GET /api/reels/products/available** first to get the list of products they can attach. Then you send that product’s ID with the video and description.
- **External:** The merchant chooses “Link to external product” and enters the **product page URL** (must be https) and **product name**. Optionally they can pick a **platform** (Flipkart, Amazon, Myntra, Other) and a **category** from your app for filtering and display. You send URL + name (and optional fields); you do **not** send `product_id`.

The backend expects **exactly one** of these two choices. If the user sends both (e.g. selected a product and also pasted a URL), or neither, the API returns 400 and you should ask them to pick one mode and fill only those fields.

---

## What you must send in every request

- **video:** The reel video file (multipart form). Allowed types: MP4, WebM, MOV. Max 100MB, max 60 seconds.
- **description:** Text description of the reel. Max 5000 characters.

Plus **either** AOIN fields **or** external fields, as below.

---

## AOIN flow (link to my product)

1. **Before opening the add-reel screen (or when the user chooses “My product”):**  
   Call **GET /api/reels/products/available** (with merchant’s auth). This returns the list of products that are approved, active, and in stock. Use this list for a product picker/dropdown.

2. **When the user submits the reel:**  
   Send in the form:
   - `video` (file)
   - `description` (text)
   - `product_id` (integer) — the ID of the product they selected from the available list.

3. **Do not send** for AOIN: `product_url`, `product_name`, or if you do, the backend will treat it as “both modes” and return 400. So when in AOIN mode, only send `product_id` in addition to `video` and `description`.

4. **What you get back:**  
   The created reel in `data` will have `product_id` set, `platform` = `"aoin"`, and `product_url` set by the backend (your app’s product page for that ID). It will also have a `product` object with name, category, stock, price. Use `product_url` for the “View product” button.

---

## External flow (link to external product)

1. **When the user chooses “External product”:**  
   Show inputs for:
   - **Product URL** (required): Must start with https. This is the link that will open when the user taps “View product”.
   - **Product name** (required): The name you show next to the reel (e.g. “Blue Running Shoes”).
   - **Platform** (optional): Dropdown or chips: Flipkart, Amazon, Myntra, Other. Default “Other” if not chosen.
   - **Category** (optional): Your app’s category list; if they pick one, send `category_id` and optionally `category_name` for display.

2. **When the user submits the reel:**  
   Send in the form:
   - `video` (file)
   - `description` (text)
   - `product_url` (the https URL they entered)
   - `product_name` (the name they entered)
   - Optionally: `platform`, `category_id`, `category_name`.

3. **Do not send** for external: `product_id`. If you send `product_id` along with URL and name, the backend returns 400 (both modes).

4. **What you get back:**  
   The created reel in `data` will have `product_id` = null, `platform` = the value you sent (or `"other"`), and `product_url` / `product_name` (and optional `category_id` / `category_name`) as stored. There is no `product` object; use the top-level `product_name` and `product_url` for display and the “View product” button.

---

## Field summary: what each field is for

| Field | Who uses it | Purpose |
|-------|-------------|---------|
| video | Both | The reel video file. |
| description | Both | Reel caption/description. |
| product_id | AOIN only | Links reel to an in-app product. |
| product_url | External only | Where “View product” goes (external site). |
| product_name | External only | Label shown for the product on the reel. |
| platform | External only | Badge/source (e.g. “Flipkart”, “Amazon”). |
| category_id | External only | Your app category for filtering/display. |
| category_name | External only | Category label for display. |

---

## Handling errors

- **400 – “Provide either product_id (AOIN) or product_url and product_name (external)”**  
  User did not complete one mode. Either they didn’t select a product (AOIN) or didn’t enter URL + name (external). Ask them to choose one type and fill the required fields.

- **400 – “Provide either ... not both”**  
  Both modes were sent (e.g. product_id and product_url). Clear one set of fields and send again.

- **400 – product_url must use https / invalid platform / category not found or inactive**  
  Show the `error` message and, if present, highlight the field in `details` (e.g. `details.field`).

- **400 – product validation (AOIN)**  
  e.g. product not found, not approved, out of stock, or not merchant’s. Refresh the available products list or ask the user to pick another product.

- **403 – Only merchants can upload reels**  
  Current user is not a merchant; hide or disable the add-reel entry point for them.

- **500**  
  Server or storage issue. Ask the user to try again later.

Use the same error shape everywhere: `error` (message), `code`, and optional `details` for logging or field-level hints.

---

## Summary

- **One API:** POST `/api/reels` with `multipart/form-data`.
- **Two modes:** AOIN (your product: send `product_id`) or external (other site: send `product_url` + `product_name`). Never both, never neither.
- **Always send:** `video` and `description`.
- **AOIN:** Get products from GET `/api/reels/products/available`; send chosen `product_id`.
- **External:** User enters URL (https) and name; optionally platform and category.
- **Response:** 201 and the created reel in `data`; use `product_url` for “View product” and `product` (AOIN) or `product_name` (external) for display.

This is the full module guide for **adding reels** only.
