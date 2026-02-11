# Reels AOIN + External – smoke test checklist

Use this list to verify the reels AOIN/external product feature after deployment or migrations.

## Upload

1. **AOIN reel** – POST `/api/reels` with `video`, `product_id`, `description`. Expect 201; response `data` has `platform: "aoin"`, `product_url` set (base URL + `/product/{id}`), `product_id` set.
2. **External reel** – POST `/api/reels` with `video`, `product_url` (https), `product_name`, `description` (no `product_id`). Expect 201; `data` has `product_id: null`, `platform` (e.g. `"other"`), `product_url` and `product_name` as sent.
3. **Reject both** – Send `product_id` and `product_url` + `product_name`. Expect 400.
4. **Reject neither** – Send only `video` and `description`. Expect 400.
5. **Invalid external** – `product_url` with `http://` or invalid scheme; or `platform` not in allowlist; or `category_id` non-existent. Expect 400.

## Feed and single reel

6. **Public feed** – GET `/api/reels/public`. Response includes both AOIN and external reels when visible.
7. **Category filter** – GET `/api/reels/public?category_id=<id>`. Includes AOIN reels with that product category and external reels with that `reel.category_id`.
8. **Single reel** – GET `/api/reels/<reel_id>` for an AOIN reel and for an external reel. AOIN has `product` object; external has `product_url`, `product_name`, `platform`, no `product` object.

## Search

9. **Search by product name** – Create an external reel with a distinct `product_name`; GET `/api/reels/search?q=<that name>`. External reel appears. Filter by `category_id` still returns external reels with that category.

## Storage

10. **S3 key for external** – After uploading an external reel, confirm object key is `reels/{merchant_id}/external/{reel_id}.mp4` (no `product-{id}` segment).
