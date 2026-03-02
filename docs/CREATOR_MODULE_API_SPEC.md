# Creator Module — API Specification (Request / Response)

This document is the **most detailed API reference** for the Creator module: **every** endpoint with **path params**, **query params**, **request body fields**, and **expected request/response** (success + all error codes). Use it together with [CREATOR_MODULE_PRD.md](./CREATOR_MODULE_PRD.md) Section 8.

**Base URL:** e.g. `https://api.aoinstore.com`  
**Auth:** `Authorization: Bearer <JWT>` for protected endpoints.  
**Error shape:** `{ "error": "<message>", "code": "<CODE>", "details": { ... } }` for 4xx/5xx.  
**Content-Type:** `application/json` unless noted (e.g. `multipart/form-data` for file upload).

---

## 1. Auth & Creator Signup

### 1.1 Signup (role creator)

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/auth/signup` | No |

**Request body fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| email | string | Yes | Valid email; unique. |
| password | string | Yes | Min length per policy. |
| first_name | string | Yes | |
| last_name | string | Yes | |
| phone | string | No | |
| role | string | Yes | Must be `"creator"` for creator signup. |

**Request:**
```json
{
  "email": "creator@example.com",
  "password": "SecurePass123",
  "first_name": "Jane",
  "last_name": "Creator",
  "phone": "+919876543210",
  "role": "creator"
}
```

**Response 201:**
```json
{
  "message": "User registered successfully",
  "user": {
    "id": 42,
    "email": "creator@example.com",
    "first_name": "Jane",
    "last_name": "Creator",
    "role": "creator",
    "is_email_verified": false
  },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 3600
}
```

**Response 400:**
```json
{
  "error": "Validation failed",
  "code": "VALIDATION_ERROR",
  "details": { "field": "email", "message": "Email already registered" }
}
```

---

### 1.2 Login

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/auth/login` | No |

**Request:** Same as existing (email/phone + password).  
**Response 200:** Tokens + user with `role: "creator"`.

---

## 2. Creator Onboarding & Profile

### 2.1 Complete onboarding

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/creator/onboarding` | Creator JWT |

**Request body fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| category_ids | array of int | Yes | At least 5 category IDs. |
| availability | string | Yes | `available` \| `busy`. |
| portfolio_links | array of string | No | URLs (e.g. Instagram, sample reels). |
| language_preferences | string | No | Optional. |

**Request:**
```json
{
  "category_ids": [1, 2, 5, 8, 12],
  "availability": "available",
  "portfolio_links": ["https://instagram.com/creator"],
  "language_preferences": "en"
}
```

**Response 201:**
```json
{
  "message": "Onboarding completed",
  "creator_profile": {
    "id": 1,
    "user_id": 42,
    "availability": "available",
    "portfolio_links": ["https://instagram.com/creator"],
    "language_preferences": "en",
    "created_at": "2026-02-24T10:00:00Z"
  },
  "categories": [
    { "category_id": 1, "name": "Electronics", "slug": "electronics" }
  ]
}
```

**Response 400:** `"At least 5 categories are required"`, details: `{ "field": "category_ids", "min_count": 5, "provided_count": 3 }`.  
**Response 409:** `"Creator profile already exists"`, code: `CONFLICT`.

---

### 2.2 Get creator profile

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/creator/profile` | Creator JWT |

**Query:** `?include_categories=1` (default true).

**Response 200:**
```json
{
  "creator_profile": {
    "id": 1,
    "user_id": 42,
    "availability": "available",
    "portfolio_links": ["https://instagram.com/creator"],
    "language_preferences": "en",
    "created_at": "2026-02-24T10:00:00Z",
    "updated_at": "2026-02-24T12:00:00Z"
  },
  "user": {
    "id": 42,
    "email": "creator@example.com",
    "first_name": "Jane",
    "last_name": "Creator",
    "profile_img": null
  },
  "categories": [
    { "category_id": 1, "name": "Electronics", "slug": "electronics" }
  ]
}
```

**Response 404:** `"Creator profile not found. Complete onboarding first."`, code: `NOT_FOUND`.

---

### 2.3 Update creator profile

| Method | Path | Auth |
|--------|------|------|
| PATCH | `/api/creator/profile` | Creator JWT |

**Request (all optional):**
```json
{
  "availability": "busy",
  "portfolio_links": ["https://instagram.com/creator", "https://tiktok.com/creator"],
  "language_preferences": "en",
  "category_ids": [1, 2, 5, 8, 12]
}
```

**Response 200:**
```json
{
  "message": "Profile updated",
  "creator_profile": {
    "id": 1,
    "user_id": 42,
    "availability": "busy",
    "portfolio_links": ["https://instagram.com/creator", "https://tiktok.com/creator"],
    "updated_at": "2026-02-24T14:00:00Z"
  }
}
```

**Response 400:** If `category_ids` &lt; 5: `"At least 5 categories are required"`.

---

### 2.4 List categories

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/categories` or `/api/creator/categories` | Optional |

**Query:** `?active_only=1`, `?parent_id=`.

**Response 200:**
```json
{
  "data": [
    { "category_id": 1, "name": "Electronics", "slug": "electronics", "parent_id": null, "is_active": true }
  ],
  "total": 50
}
```

---

## 3. Campaigns — Merchant

### 3.1 Discover creators

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/campaigns/creators` | Merchant JWT |

**Query parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| category_id | int | No | — | Match creators who have this category. |
| availability | string | No | — | `available` \| `busy`. |
| page | int | No | 1 | Page number. |
| per_page | int | No | 20 | Max 50. |
| q | string | No | — | Search name/email. |

**Response 200:**
```json
{
  "data": [
    {
      "creator_id": 1,
      "user_id": 42,
      "first_name": "Jane",
      "last_name": "Creator",
      "profile_img": null,
      "availability": "available",
      "portfolio_links": ["https://instagram.com/creator"],
      "categories": [
        { "category_id": 1, "name": "Electronics" },
        { "category_id": 2, "name": "Fashion" }
      ]
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total": 15 }
}
```

---

### 3.2 Create campaign (draft)

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/campaigns` | Merchant JWT |

**Request body fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| product_id | int | Yes | Merchant's AOIN product. |
| creator_id | int | Yes | creator_profiles.id. |
| commission_type | string | Yes | `percent_capped` \| `percent_unlimited`. |
| commission_percent | decimal | Yes | e.g. 20.00. |
| commission_cap_quantity | int | No | For percent_capped; max units. |
| campaign_window_start | datetime | No | ISO 8601. |
| campaign_window_end | datetime | No | ISO 8601. |
| deliverable_type | string | No | V1 default `1_reel`. |

**Request:**
```json
{
  "product_id": 101,
  "creator_id": 1,
  "commission_type": "percent_capped",
  "commission_percent": 20,
  "commission_cap_quantity": 200,
  "campaign_window_start": "2026-03-01T00:00:00Z",
  "campaign_window_end": "2026-03-31T23:59:59Z",
  "deliverable_type": "1_reel"
}
```

**Response 201:**
```json
{
  "message": "Campaign created",
  "campaign": {
    "campaign_id": 5,
    "campaign_code": "CAMP-A7X2",
    "merchant_id": 10,
    "creator_id": 1,
    "product_id": 101,
    "status": "draft",
    "commission_type": "percent_capped",
    "commission_percent": 20,
    "commission_cap_quantity": 200,
    "campaign_window_start": "2026-03-01T00:00:00Z",
    "campaign_window_end": "2026-03-31T23:59:59Z",
    "deliverable_type": "1_reel",
    "created_at": "2026-02-24T10:00:00Z"
  },
  "product": { "product_id": 101, "product_name": "Wireless Earbuds", "category_id": 1 },
  "creator": { "creator_id": 1, "first_name": "Jane", "last_name": "Creator" }
}
```

**Response 400:** e.g. `"Product does not belong to merchant"`, details: `{ "field": "product_id" }`.

---

### 3.3 Send campaign

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/campaigns/:id/send` | Merchant JWT |

**Path parameters:**

| Param | Type | Description |
|-------|------|-------------|
| id | int | campaign_id. |

**Request:** No body (or `{}`).

**Response 200:**
```json
{
  "message": "Campaign sent to creator",
  "campaign": {
    "campaign_id": 5,
    "campaign_code": "CAMP-A7X2",
    "status": "sent",
    "sent_at": "2026-02-24T10:05:00Z"
  }
}
```

**Response 400:** `"Campaign can only be sent from draft status"`, code: `INVALID_STATE`, details: `{ "current_status": "active" }`.

---

### 3.4 List merchant campaigns

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/campaigns` | Merchant JWT |

**Query:** `status`, `page`, `per_page`.

**Response 200:**
```json
{
  "data": [
    {
      "campaign_id": 5,
      "campaign_code": "CAMP-A7X2",
      "product_id": 101,
      "product_name": "Wireless Earbuds",
      "creator_id": 1,
      "creator_name": "Jane Creator",
      "status": "active",
      "commission_percent": 20,
      "commission_cap_quantity": 200,
      "created_at": "2026-02-24T10:00:00Z",
      "reels_count": 0,
      "pending_reels_count": 0
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total": 3 }
}
```

---

### 3.5 Get campaign by ID (merchant)

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/campaigns/:id` | Merchant JWT |

**Response 200:**
```json
{
  "campaign": {
    "campaign_id": 5,
    "campaign_code": "CAMP-A7X2",
    "merchant_id": 10,
    "creator_id": 1,
    "product_id": 101,
    "status": "active",
    "commission_type": "percent_capped",
    "commission_percent": 20,
    "commission_cap_quantity": 200,
    "campaign_window_start": "2026-03-01T00:00:00Z",
    "campaign_window_end": "2026-03-31T23:59:59Z",
    "deliverable_type": "1_reel",
    "created_at": "2026-02-24T10:00:00Z",
    "sent_at": "2026-02-24T10:05:00Z",
    "accepted_at": "2026-02-24T11:00:00Z"
  },
  "product": { "product_id": 101, "product_name": "Wireless Earbuds", "category_id": 1, "selling_price": "1999.00" },
  "creator": { "creator_id": 1, "first_name": "Jane", "last_name": "Creator", "availability": "available" },
  "reels": [
    { "reel_id": 20, "approval_status": "pending", "created_at": "2026-02-24T12:00:00Z", "description": "Unboxing video" }
  ]
}
```

**Response 404:** Campaign not found or not merchant's.

---

### 3.6 Cancel campaign

| Method | Path | Auth |
|--------|------|------|
| PATCH | `/api/campaigns/:id` | Merchant JWT |

**Request:**
```json
{
  "action": "cancel",
  "reason": "Product out of stock"
}
```

**Response 200:**
```json
{
  "message": "Campaign cancelled",
  "campaign": {
    "campaign_id": 5,
    "status": "cancelled",
    "updated_at": "2026-02-24T14:00:00Z"
  }
}
```

**Response 400:** `"Campaign cannot be cancelled in current status"`, code: `INVALID_STATE`.

---

### 3.7 Extend campaign window

| Method | Path | Auth |
|--------|------|------|
| PATCH | `/api/campaigns/:id` | Merchant JWT |

**Request:**
```json
{
  "action": "extend",
  "campaign_window_end": "2026-04-15T23:59:59Z"
}
```

**Response 200:** Updated campaign with new `campaign_window_end`.

---

## 4. Campaigns — Creator

### 4.1 List my campaigns

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/creator/campaigns` | Creator JWT |

**Query:** `status`, `page`, `per_page`.

**Response 200:**
```json
{
  "data": [
    {
      "campaign_id": 5,
      "campaign_code": "CAMP-A7X2",
      "status": "sent",
      "product": { "product_id": 101, "product_name": "Wireless Earbuds", "selling_price": "1999.00" },
      "merchant": { "merchant_id": 10, "business_name": "Tech Store" },
      "commission_percent": 20,
      "commission_cap_quantity": 200,
      "campaign_window_end": "2026-03-31T23:59:59Z",
      "sent_at": "2026-02-24T10:05:00Z"
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total": 2 }
}
```

---

### 4.2 Get my campaign by ID

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/creator/campaigns/:id` | Creator JWT |

**Response 200:** Same shape as 3.5; only campaigns assigned to this creator.  
**Response 404:** Not found or not assigned.

---

### 4.3 Accept campaign

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/creator/campaigns/:id/accept` | Creator JWT |

**Request:** No body.

**Response 200:**
```json
{
  "message": "Campaign accepted",
  "campaign": {
    "campaign_id": 5,
    "campaign_code": "CAMP-A7X2",
    "status": "active",
    "accepted_at": "2026-02-24T11:00:00Z"
  }
}
```

**Response 400:** `"Only campaigns with status 'sent' can be accepted"`, code: `INVALID_STATE`.

---

### 4.4 Reject campaign

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/creator/campaigns/:id/reject` | Creator JWT |

**Request (optional):**
```json
{
  "reason": "Not enough time before deadline"
}
```

**Response 200:**
```json
{
  "message": "Campaign rejected",
  "campaign": {
    "campaign_id": 5,
    "status": "rejected"
  }
}
```

---

### 4.5 List active campaigns (dropdown)

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/creator/campaigns/active` | Creator JWT |

**Response 200:**
```json
{
  "data": [
    {
      "campaign_id": 5,
      "campaign_code": "CAMP-A7X2",
      "product_name": "Wireless Earbuds",
      "merchant_business_name": "Tech Store",
      "campaign_window_end": "2026-03-31T23:59:59Z"
    }
  ]
}
```

---

## 5. Creator Reel Upload

### 5.1 Upload reel (campaign-linked)

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/creator/reels` | Creator JWT |

**Content-Type:** `multipart/form-data`.

**Request body (form fields):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| campaign_id | int | Yes | Active campaign assigned to this creator. |
| video | file | Yes | mp4, webm, mov; max size per policy. |
| description | string | Yes | Max length e.g. 5000. |

**Response 201:**
```json
{
  "message": "Reel submitted for merchant approval",
  "reel": {
    "reel_id": 20,
    "campaign_id": 5,
    "merchant_id": 10,
    "product_id": 101,
    "approval_status": "pending",
    "video_url": "https://cdn.../reel-20.mp4",
    "thumbnail_url": "https://cdn.../thumb-20.jpg",
    "description": "Unboxing video",
    "created_at": "2026-02-24T12:00:00Z"
  }
}
```

**Response 400:** `"Campaign is not active or not assigned to you"`, details: `{ "field": "campaign_id", "campaign_id": 5 }`.  
**Response 413:** File too large.

---

## 6. Reels — Merchant Approval

### 6.1 List pending reels for campaign

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/campaigns/:id/reels/pending` | Merchant JWT |

**Response 200:**
```json
{
  "data": [
    {
      "reel_id": 20,
      "campaign_id": 5,
      "description": "Unboxing video",
      "video_url": "https://cdn.../reel-20.mp4",
      "thumbnail_url": "https://cdn.../thumb-20.jpg",
      "approval_status": "pending",
      "created_at": "2026-02-24T12:00:00Z",
      "creator": { "creator_id": 1, "first_name": "Jane", "last_name": "Creator" }
    }
  ]
}
```

---

### 6.2 Approve reel

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/reels/:id/approve` | Merchant JWT |

**Request:** No body.

**Response 200:**
```json
{
  "message": "Reel approved",
  "reel": {
    "reel_id": 20,
    "approval_status": "approved",
    "approved_at": "2026-02-24T14:00:00Z",
    "approved_by": 10
  }
}
```

**Response 400:** `"Reel is not pending approval or does not belong to your campaign"`, code: `INVALID_STATE`.

---

### 6.3 Reject reel

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/reels/:id/reject` | Merchant JWT |

**Request:**
```json
{
  "reason": "Product not clearly visible; please reshoot with product in frame"
}
```

**Response 200:**
```json
{
  "message": "Reel rejected",
  "reel": {
    "reel_id": 20,
    "approval_status": "rejected",
    "rejection_reason": "Product not clearly visible; please reshoot with product in frame"
  }
}
```

---

## 7. Attribution

### 7.1 Record reel → product click

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/attribution/click` | User JWT or guest |

**Request body fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| reel_id | int | Yes | Reel from which user clicked. |
| product_id | int | Yes | Product opened. |

**Request:**
```json
{
  "reel_id": 20,
  "product_id": 101
}
```

**Response 201:**
```json
{
  "message": "Click recorded",
  "attribution_event": {
    "id": 1001,
    "user_id": 55,
    "reel_id": 20,
    "campaign_id": 5,
    "product_id": 101,
    "clicked_at": "2026-02-24T15:30:00Z"
  }
}
```

**Response 400:** `"Reel or product not found"`, details: `{ "reel_id": 20, "product_id": 101 }`.

---

## 8. Creator Earnings & Settlement

### 8.1 Earnings summary

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/creator/earnings/summary` | Creator JWT |

**Response 200:**
```json
{
  "pending_amount": "0.00",
  "eligible_amount": "1250.50",
  "paid_amount": "3200.00",
  "currency": "INR",
  "pending_count": 0,
  "eligible_count": 5,
  "paid_count": 12
}
```

---

### 8.2 List earnings

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/creator/earnings` | Creator JWT |

**Query:** `status` (pending|eligible|paid), `page`, `per_page`, `from_date`, `to_date`.

**Response 200:**
```json
{
  "data": [
    {
      "id": 501,
      "order_item_id": 1001,
      "campaign_id": 5,
      "campaign_code": "CAMP-A7X2",
      "product_name": "Wireless Earbuds",
      "eligible_amount": "350.00",
      "creator_commission_amount": "70.00",
      "platform_fee_amount": "17.50",
      "status": "eligible",
      "created_at": "2026-02-24T16:00:00Z"
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total": 5 }
}
```

---

### 8.3 Get payout detail

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/creator/payouts/:id` | Creator JWT |

**Response 200:**
```json
{
  "payout": {
    "id": 10,
    "creator_id": 1,
    "amount": "1250.50",
    "status": "completed",
    "period_start": "2026-02-01T00:00:00Z",
    "period_end": "2026-02-28T23:59:59Z",
    "paid_at": "2026-03-05T10:00:00Z",
    "reference": "TXN123456"
  },
  "ledger_entries_count": 8
}
```

---

## 9. Merchant Settlement

### 9.1 Get campaign settlement

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/merchant/campaigns/:id/settlement` | Merchant JWT |

**Query:** `status`, `from_date`, `to_date`, `page`, `per_page`.

**Response 200:**
```json
{
  "campaign": {
    "campaign_id": 5,
    "campaign_code": "CAMP-A7X2",
    "creator_name": "Jane Creator",
    "product_name": "Wireless Earbuds",
    "commission_percent": 20,
    "commission_cap_quantity": 200
  },
  "summary": {
    "total_attributed_sales_count": 15,
    "total_eligible_amount": "45000.00",
    "total_creator_commission": "9000.00",
    "total_platform_fee": "2250.00",
    "total_merchant_net": "33750.00",
    "currency": "INR"
  },
  "data": [
    {
      "order_item_id": 1001,
      "order_id": "ORD-20260224001",
      "product_name": "Wireless Earbuds",
      "quantity": 2,
      "eligible_amount": "3500.00",
      "creator_commission_amount": "700.00",
      "platform_fee_amount": "175.00",
      "merchant_net_amount": "2625.00",
      "status": "paid",
      "created_at": "2026-02-24T16:00:00Z"
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total": 15 }
}
```

**Response 404:** Campaign not found or not merchant's.

---

## 10. Reels (read) — Optional response changes

- **GET /api/reels**, **GET /api/reels/:id:** Add to reel object when creator-uploaded: `campaign_id`, `campaign_code`, `creator`: `{ "creator_id", "first_name", "last_name" }`. No request change.

---

## 11. Admin (optional V1)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/admin/campaigns` | Admin | List all campaigns |
| PATCH | `/api/admin/campaigns/:id` | Admin | Override status |
| GET | `/api/admin/settlement/ledger` | Admin | View ledger |
| POST | `/api/admin/settlement/run-eligibility` | Admin | Run eligibility job |
| POST | `/api/admin/settlement/run-payout` | Admin | Run payout job |

Request/response: same patterns as above (list + pagination, single resource, action in body).
