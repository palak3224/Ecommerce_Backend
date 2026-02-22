# Multi‑Platform Product Reels (V1) — Feature Notes

## Context (current behavior)

- Reels today are **AOIN-only** because `Reel.product_id` is **required** (`nullable=False`) and all reel visibility/serialization depends on the AOIN `Product`:
  - Stock must be > 0
  - Product must be approved + active + not deleted
  - Product must belong to the merchant
- “Recently viewed reels” uses `user_reel_views` and only shows reels that are `approved`, `is_active`, and `is_visible` (where `is_visible` currently depends on AOIN product conditions).

## Goal

Allow merchants to upload reels in **two ways**:

1. **AOIN product reel** (existing flow): reel is linked to an internal AOIN product.
2. **External platform product reel** (new flow): reel promotes a product on another platform (e.g., Amazon/Flipkart/etc.), and the reel stores a lightweight product “snapshot” (price/category/image/link/platform) so the feed has everything it needs.

## V1 design (keep it simple)

### Key concept: reel `type`

- Add `type` (or `product_source`) to reels with two values:
  - `aoin` (internal)
  - `external` (other platforms)

### Single upload endpoint, two modes

Keep the same endpoint: **`POST /api/reels`** (multipart/form-data), but validate based on `type`.

#### Product URL: required for both types

- **`product_url`** is **required for both AOIN and external reels** and stored in the same column (`reels.product_url`). This keeps link handling unified: the frontend can always use `reel.product_url` for the “Buy” / product link.
- Must be a valid URL (e.g. https). For AOIN, this is typically the store’s product page URL (e.g. `https://yoursite.com/product/123`). For external, it is the external platform product link.

#### Mode A: `type="aoin"` (current flow)

- Required:
  - `video` (file)
  - `description` (string)
  - `product_id` (int)
  - **`product_url`** (string; product page URL, e.g. AOIN product detail link)
- Backend continues to derive:
  - category, price, product info, product image(s) from AOIN product tables.
- Backend stores the provided `product_url` on the reel (no longer derived from config).

#### Mode B: `type="external"` (new flow)

Required (minimal, enough to render a full card in feed):
- `video` (file)
- `description` (string)
- **`product_url`** (string; clickable external link) — required for both types
- `platform_name` (string; free-text in V1, dropdown later)
- `category` (string)
- `price` (number) + `currency` (string like `INR`)
- **product image**:
  - simplest: `product_image_url` (string)
  - optional alternative (if desired): `product_image` (file upload) stored via Cloudinary/S3 like other media

**Important V1 decision**: no scraping. Merchant supplies the fields (snapshot).

### “Synced” meaning in V1

- **AOIN reels** stay synced through `product_id` and live product data.
- **External reels** are “synced” via a stored snapshot so the reel always renders consistently, even if the external page changes.

## Validation rules (V1)

### Product URL (required for both)

- **`product_url`** is required for both AOIN and external reels.
- Must be a valid URL (https, non-empty, within length limit). Stored in `reels.product_url` for both types.

### Mutually exclusive requirements

- If `type="aoin"`:
  - `product_id` and **`product_url`** are required
  - external-only fields (e.g. product_name, platform) are ignored or rejected
- If `type="external"`:
  - `product_id` must be absent/null
  - **`product_url`** and all other external required fields must be present

### URL rules

- Must be a valid URL (https).
- (Optional) V1 allowlist of domains for external (to reduce abuse): `amazon.*`, `flipkart.*`, etc.

## Visibility rules (V1)

### AOIN reels
Keep existing visibility logic (stock/approval/ownership checks).

### External reels
Keep simple:
- visible if reel is active + not deleted **and** external required fields exist
- **no stock checks**, **no AOIN approval checks** for external

## API response shape (frontend-friendly)

To keep frontend changes small, return a unified shape:

- Common reel fields (existing): `reel_id`, `merchant_id`, `video_url`, `thumbnail_url`, `description`, stats, timestamps, `type`
- **`product_url`** is always present for both types (stored on the reel); use it for the product / “Buy” link.
- For `type="aoin"`:
  - include existing `product` object (from AOIN)
- For `type="external"`:
  - include `external_product` object:
    - `product_url`
    - `platform_name`
    - `category`
    - `price`
    - `currency`
    - `product_image_url`

Frontend logic:
- Use `reel.product_url` for the product link in both cases.
- If `type==="aoin"` render AOIN product card.
- Else render external card + “Buy on {platform}” link.

## Backend changes (when implementing)

### Database / model

- `reels.product_id` must become **nullable** to support external reels.
- Add columns for external snapshot (either as columns or a JSON column):
  - `type` (`aoin`/`external`)
  - `external_product_url`
  - `external_platform_name`
  - `external_category`
  - `external_price`
  - `external_currency`
  - `external_product_image_url`

### Reel visibility + serialize

- Update `Reel.get_disabling_reasons()` and `Reel.serialize()` so:
  - `type="aoin"` behaves exactly as today
  - `type="external"` does not require `self.product`, and checks the external snapshot fields instead

### Upload controller

- Update `ReelsController.upload_reel()` to:
  - require **`product_url`** for both AOIN and external reels (validate URL format; store in `reels.product_url`)
  - accept `type` (or infer from product_id vs product_name)
  - branch validation for AOIN vs external
  - for AOIN: store the provided `product_url` on the reel (do not derive from config)
  - store external snapshot fields when external

## Frontend changes (when implementing)

### Merchant upload UI

- Add a toggle:
  - “AOIN product” vs “External product”
- **Product URL**: show one “Product URL” field for both types (required). For AOIN, frontend may pre-fill from selected product (e.g. `window.location.origin + '/product/' + product_id`) or let the merchant paste it.
- If AOIN:
  - show product picker (existing) and product URL input (required)
- If External:
  - show inputs: product URL (required), platform, category, price, currency, image URL/upload

### Feed rendering

- Render based on `reel.type`.
- External reels should open external URL in a new tab / external browser.

## Out of scope for V1 (explicitly not doing now)

- Automatic scraping of external URLs for title/price/category/image
- Real-time external price syncing
- Affiliate tracking / deep integrations
- Complex category mapping to internal category IDs
- Additional moderation workflow (optional later; can be added if abuse becomes an issue)

## Optional V2 ideas

- Domain allowlist + stronger validation
- Platform enum instead of free text
- Internal category mapping for better filtering/recommendations
- Admin approval for external reels or restriction to verified merchants

