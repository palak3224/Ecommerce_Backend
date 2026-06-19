# Product Details API — Mobile Integration Guide

How to fetch a single product's details for the app. Two endpoints are available;
**use `/details` for a product page** (it returns media, attributes, variants,
reviews, brand, category). Use the basic one only when you need a lightweight object.

| Use case | Endpoint |
|----------|----------|
| **Full product page** (recommended) | `GET /api/products/{product_id}/details` |
| Lightweight single product | `GET /api/products/{product_id}` |

Base URL: prepend your host, e.g. `https://api.aoinstore.com`.

---

## GET /api/products/{product_id}/details

Returns full details for one product.

- **Auth:** optional. No token works (public). If a **Bearer token** is sent, the
  view is recorded in the user's "recently viewed" list — otherwise identical.
- **Visibility:** only **approved, active, non-deleted** products from **open
  merchants** are returned; anything else → `404`.

### Path parameters

| Param | Type | Description |
|-------|------|-------------|
| `product_id` | integer | The product's numeric ID |

### Example

```
GET /api/products/123/details
# optional, for recently-viewed tracking:
Authorization: Bearer <access_token>
```

### Success — `200 OK`

```json
{
  "product_id": 123,
  "id": "123",
  "name": "Cotton Casual Shirt",
  "product_name": "Cotton Casual Shirt",
  "product_description": "Soft breathable cotton shirt.",
  "sku": "SHIRT-BLUE-M",

  "merchant_id": 51,
  "category_id": 7,
  "category_name": "Shirts",
  "brand_id": 4,
  "brand_name": "Acme",

  "cost_price": 800.0,
  "selling_price": 1299.0,
  "special_price": 999.0,
  "special_start": "2026-06-01T00:00:00",
  "special_end": "2026-06-30T00:00:00",
  "is_on_special_offer": true,
  "price": 999.0,
  "originalPrice": 1299.0,
  "currency": "INR",

  "stock": 24,
  "rating": 4.3,
  "active_flag": true,
  "approval_status": "approved",

  "parent_product_id": null,
  "is_variant": false,

  "media": [
    {
      "media_id": 900,
      "url": "https://cdn.aoinstore.com/products/123/main.jpg",
      "type": "image",
      "is_main_image": true,
      "is_thumbnail": false,
      "sort_order": 0
    }
  ],

  "meta": {
    "short_desc": "Soft breathable cotton shirt.",
    "full_desc": "<p>Full HTML description…</p>",
    "meta_title": "Cotton Casual Shirt",
    "meta_desc": "Buy cotton casual shirt…",
    "meta_keywords": "shirt, cotton, casual"
  },

  "attributes": [
    {
      "attribute_id": 12,
      "attribute_name": "Color",
      "value_code": "blue",
      "value_text": "Blue",
      "value_label": "Blue",
      "is_text_based": false,
      "input_type": "select"
    }
  ],

  "category": { "category_id": 7, "name": "Shirts" },
  "brand":    { "brand_id": 4, "name": "Acme" },

  "variants": [
    {
      "id": "124",
      "name": "Cotton Casual Shirt - L",
      "price": 999.0,
      "originalPrice": 1299.0,
      "sku": "SHIRT-BLUE-L",
      "isVariant": true,
      "isParent": false,
      "parentProductId": "123",
      "media": [ { "url": "https://cdn.aoinstore.com/products/124/main.jpg", "type": "image" } ]
    }
  ],

  "reviews": [
    {
      "id": 5001,
      "user": { "id": 42, "first_name": "Bob", "last_name": "B", "email": "b@x.com", "avatar": null },
      "rating": 5,
      "title": "Great fit",
      "body": "Very comfortable.",
      "created_at": "2026-06-10T12:00:00",
      "images": [ { "url": "https://cdn.aoinstore.com/reviews/5001/1.jpg" } ]
    }
  ]
}
```

### Key fields for the app

| Field | Meaning |
|-------|---------|
| `price` | **The price to display** (already reflects active special offer, GST-inclusive) |
| `originalPrice` | Struck-through original price; `null` when no offer is active |
| `is_on_special_offer` | Whether `price` is a discounted special price |
| `currency` | Always `"INR"` |
| `stock` | Quantity available (`0` = out of stock) |
| `rating` | Average review rating (0–5, 1 decimal) |
| `media[]` | Ordered images/videos — **thumbnail → main → others**; use `media[0]` as primary |
| `attributes[]` | Color/Size/etc. (`attribute_name` + `value_text`) |
| `variants[]` | Other sizes/colors; each has its own `id`, `price`, `media` — fetch its `/details` to switch |
| `reviews[]` | Recent reviews, newest first |
| `parent_product_id` / `is_variant` | If `is_variant` is true, this is one variant of a parent |

### Errors

| Status | Body | When |
|--------|------|------|
| `404` | `{ "error": "Not found" }` (or 404 page) | Product missing / not approved / merchant closed |
| `500` | `{ "error": "Failed to fetch product details", "message": "..." }` | Server error |

---

## GET /api/products/{product_id} (lightweight)

Same product object **without** the extra `media`/`reviews`/`variants` enrichment —
returns the base serialized product (still includes `price`, `originalPrice`,
`stock`, `attributes`, `selling_price`, etc.). Public, no auth.

```
GET /api/products/123
```

Use `/details` for the product page; this one is fine for quick lookups.

---

## Notes for integration

- **Price:** always show `price`; show `originalPrice` struck-through only when it's
  non-null. Don't compute discounts client-side — the backend already resolves the
  active offer and GST-inclusive amount.
- **Images:** `media` is pre-sorted; `media[0]` is the best primary image.
- **Out of stock:** `stock === 0`.
- **Recently viewed:** send the user's `Authorization: Bearer <token>` on `/details`
  if you want the view tracked; otherwise omit it.
- **Variants:** to show a size/color switcher, read `variants[]`; tapping one should
  load that variant via its own `id` (`/api/products/{id}/details`).

---

## Related product endpoints (for context)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/products` | List/browse with filters & pagination |
| `GET` | `/api/products/category/{category_id}` | Products in a category |
| `GET` | `/api/products/brand/{brand_slug}` | Products of a brand |
| `GET` | `/api/products/{product_id}/variants` | Just the variant list |
| `GET` | `/api/products/{product_id}/reviews` | Paginated reviews + average rating |
| `GET` | `/api/products/search-suggestions?q=...` | Search autocomplete |
