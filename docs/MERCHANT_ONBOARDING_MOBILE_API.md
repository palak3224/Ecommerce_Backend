# Merchant / Vendor Onboarding API — Mobile Integration Guide

This document describes the **complete merchant onboarding flow** as implemented on
the website, so the mobile app can replicate it 1:1. It covers registration, email
verification, login, country-driven document requirements, KYC document upload, and
checking verification status.

> All request/response shapes below match the live backend exactly.

---

## Base URLs & prefixes

| Area | Prefix |
|------|--------|
| Auth (register, login, verify, profile) | `/api/auth` |
| Country config | `/api/merchants` |
| KYC documents | `/api/merchant/documents` |

Set a single host base (e.g. `https://api.aoinstore.com`) and prepend it to the
paths below.

---

## The onboarding flow at a glance

```
1. Register merchant            POST /api/auth/register/merchant   { ..., "source": "app" }
2. Verify business email (OTP)  POST /api/auth/merchant/verify-email-otp   { email, otp }
       └─ (resend code)         POST /api/auth/merchant/resend-email-otp   { email }
3. Merchant login               POST /api/auth/login   (use business_email!)
4. Load country requirements    GET  /api/merchants/country-config/<country_code>
5. Upload each KYC document     POST /api/merchant/documents/upload   (multipart)
6. Poll verification status     GET  /api/auth/merchant/profile
       └─ admin approves/rejects on their side
```

> **📱 App vs. Web verification.** This is the only step that differs by platform.
> The **mobile app** sends `"source": "app"` at registration, and the backend
> emails a **6-digit OTP** the user types into the app — no browser needed. The
> **website** omits `source` and gets a clickable email link instead. Everything
> else (login, KYC, status) is identical. The OTP flow is the same on Android and
> iOS. See [Step 2](#step-2--verify-business-email-otp-app-flow).

Verification status progresses:
`pending → email_verified → documents_submitted → under_review → approved | rejected`

- Registering creates the account at **`pending`**.
- Verifying the email moves it to **`email_verified`**.
- Uploading the first document auto-submits for verification (**`documents_submitted`**).
- Admin review ends at **`approved`** or **`rejected`**.

---

## Step 1 — Register merchant

**`POST /api/auth/register/merchant`** · no auth

### Request body (JSON)

```json
{
  "first_name": "Asha",
  "last_name": "Verma",
  "password": "StrongPass123",
  "phone": "+919876543210",
  "business_name": "Asha Crafts",
  "business_description": "Handmade home decor",
  "business_email": "seller@ashacrafts.com",
  "business_phone": "+91 98765 43210",
  "business_address": "12 MG Road",
  "country_code": "IN",
  "state_province": "Maharashtra",
  "city": "Pune",
  "postal_code": "411001",
  "username": "asha_crafts",
  "source": "app"
}
```

> **Mobile app must send `"source": "app"`.** This switches verification to the
> OTP-by-email flow (Step 2). Omit it (or send `"web"`) to get the link flow.

| Field | Required | Rules |
|-------|----------|-------|
| `first_name`, `last_name` | ✅ | string |
| `password` | ✅ | min 8 chars |
| `business_name` | ✅ | string |
| `business_email` | ✅ | valid email — **this becomes the login email** |
| `business_phone` | ✅ | 10–30 chars; digits, spaces, `+ - ( )` only; must contain a digit; cannot be an email |
| `country_code` | ✅ | `"IN"` or `"GLOBAL"` (see [Country codes](#country-codes)) |
| `state_province`, `city`, `postal_code` | ✅ | string |
| `phone` | ❌ | personal phone |
| `business_description`, `business_address` | ❌ | string |
| `username` | ❌ | 3–30 chars, `[a-zA-Z0-9_]`. **Auto-generated** from business name if omitted |
| `source` | ❌ | `"app"` (OTP flow) or `"web"` (link flow, default). **App must send `"app"`.** |

### Success — `201 Created`

For the **app** flow (`source:"app"`):

```json
{
  "message": "Merchant registered successfully. Please check your email for the verification code.",
  "user_id": 105,
  "merchant_id": 51,
  "username": "asha_crafts",
  "verification_method": "otp"
}
```

For the **web** flow (no `source`):

```json
{
  "message": "Merchant registered successfully. Please check your email to verify your account.",
  "user_id": 105,
  "merchant_id": 51,
  "username": "asha_crafts",
  "verification_method": "link"
}
```

> **`verification_method`** tells the app which Step 2 to run: `"otp"` → call
> `verify-email-otp`; `"link"` → user verifies via the emailed link.
>
> **Dev/QA only:** when the server has `DEV_OTP_BYPASS` enabled, the app-flow
> response also includes `"dev_otp": "483920"` so testers can verify without a real
> inbox. This field is **never** present in production.

If the verification email could not be sent, you'll additionally get:

```json
{
  "message": "Merchant registered successfully. Verification email could not be sent. Please use the resend email feature.",
  "user_id": 105,
  "merchant_id": 51,
  "username": "asha_crafts",
  "warning": "Verification email not sent. Please use the resend email feature.",
  "email_sent": false
}
```

### Errors

| Status | Body | When |
|--------|------|------|
| `400` | `{ "error": "Validation error", "details": { ... } }` | Field validation failed (per-field messages in `details`) |
| `409` | `{ "error": "Business email already registered" }` | Email in use |
| `409` | `{ "error": "Username already taken" }` | Username in use |
| `500` | `{ "error": "Registration failed", "details": "..." }` | Server error |

---

## Step 2 — Verify business email (OTP, app flow)

When the merchant registered with `source:"app"`, they receive a **6-digit OTP by
email**. The app collects that code and submits it here — no browser, no deep link.

**`POST /api/auth/merchant/verify-email-otp`** · no auth

### Request body

```json
{
  "email": "seller@ashacrafts.com",
  "otp": "483920"
}
```

| Field | Required | Rules |
|-------|----------|-------|
| `email` | ✅ | the `business_email` used at registration |
| `otp` | ✅ | exactly 6 digits |

### Success — `200 OK`

The merchant is verified **and logged in** — the response returns tokens plus the
user and merchant objects, so the app can go straight to the dashboard / KYC step
without a separate login call.

```json
{
  "message": "Email verified successfully",
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": {
    "id": 105,
    "email": "seller@ashacrafts.com",
    "first_name": "Asha",
    "last_name": "Verma",
    "role": "merchant",
    "is_email_verified": true
  },
  "merchant": {
    "id": 51,
    "user_id": 105,
    "business_name": "Asha Crafts",
    "business_email": "seller@ashacrafts.com",
    "verification_status": "email_verified",
    "is_verified": false
  }
}
```

> Store `access_token`/`refresh_token` here — the merchant is now authenticated and
> can proceed to Step 4/5. (Step 3 login is then optional for this session, but
> still used for future logins.)

### Errors

| Status | Body | When |
|--------|------|------|
| `400` | `{ "error": "Validation error", "details": { ... } }` | `otp` not 6 chars / missing field |
| `400` | `{ "error": "Invalid or expired OTP" }` | Wrong or expired code |
| `403` | `{ "error": "This verification method is only for merchant accounts." }` | Email isn't a merchant |
| `500` | `{ "error": "Email verification failed" }` | Server error |

> **Idempotent:** if the account is already verified, this returns `200` with a
> fresh session (so a retried request is safe).

### Resend the OTP

**`POST /api/auth/merchant/resend-email-otp`** · no auth

```json
{ "email": "seller@ashacrafts.com" }
```

Returns `200` with a generic message (always generic, to avoid leaking which emails
exist). Throttled:

| Status | Body | When |
|--------|------|------|
| `200` | `{ "message": "If your email is registered and not verified, a new code has been sent." }` | Sent (or generic no-op) |
| `200` | `{ "message": "Your email address is already verified." }` | Nothing to do |
| `429` | `{ "error_code": "RATE_LIMIT_APPLIED", "message": "Please wait before requesting another code.", "retry_after": 30 }` | Requested again too soon (30s min) |
| `429` | `{ "error_code": "RATE_LIMIT_EXCEEDED", ... }` | Daily cap reached |

> Each resend invalidates any previous unused OTP — only the latest code works.
> A new OTP also resets the 10-minute expiry.

---

## Step 2 (alt) — Verify business email via link (web flow)

For the **web** flow (registered without `source`), the email contains a clickable
link to:

**`GET /api/auth/verify-email/<token>`** · no auth

The website handles this automatically. **The mobile app should use the OTP flow
above instead** and does not need this endpoint. (Resend link, web only:
`POST /api/auth/verify-email/resend` with `{ "email": "..." }`.)

---

## Step 3 — Merchant login

**`POST /api/auth/login`** · no auth

> ⚠️ **Merchants must log in with `business_email`, NOT `email`.** Logging in via the
> `email` field for a merchant account is rejected with `403`
> (`"Merchants must sign in through the merchant dashboard."`).

### Request body

```json
{
  "business_email": "seller@ashacrafts.com",
  "password": "StrongPass123"
}
```

### Success — `200 OK`

```json
{
  "message": "Merchant login successful",
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": {
    "id": 105,
    "email": "seller@ashacrafts.com",
    "first_name": "Asha",
    "last_name": "Verma",
    "role": "merchant",
    "is_email_verified": true
  },
  "merchant": {
    "id": 51,
    "user_id": 105,
    "business_name": "Asha Crafts",
    "business_email": "seller@ashacrafts.com",
    "business_phone": "+91 98765 43210",
    "business_address": "12 MG Road",
    "gstin": null,
    "pan_number": null,
    "bank_account_number": null,
    "bank_ifsc_code": null,
    "verification_status": "email_verified",
    "verification_submitted_at": null,
    "verification_completed_at": null,
    "verification_notes": null,
    "is_verified": false,
    "can_place_premium": false,
    "created_at": "2026-06-17T10:00:00",
    "updated_at": "2026-06-17T10:05:00"
  }
}
```

Use `access_token` as `Authorization: Bearer <token>` on all subsequent calls.

### Errors

| Status | Body | When |
|--------|------|------|
| `401` | `{ "error": "Invalid email or password" }` | Bad credentials |
| `403` | `{ "error_code": "EMAIL_NOT_VERIFIED", "message": "Please verify your email address to log in.", "email": "..." }` | Email not yet verified → send user back to Step 2 |
| `403` | `{ "error": "Account is disabled" }` | Account disabled |
| `400` | `{ "error": "Validation error", "details": { ... } }` | Missing fields |

> Handle `error_code: "EMAIL_NOT_VERIFIED"` specifically — show a "resend email"
> CTA wired to Step 2's resend endpoint.

---

## Step 4 — Load country document requirements

Drives the dynamic KYC form. Call this to know which documents and bank/tax fields
apply for the merchant's country.

**`GET /api/merchants/country-config/<country_code>`** · no auth

Example: `GET /api/merchants/country-config/IN`

### Success — `200 OK`

```json
{
  "country_code": "IN",
  "country_name": "India",
  "required_documents": [
    { "type": "pan_card", "name": "Pan Card", "required": true },
    { "type": "aadhar", "name": "Aadhar", "required": true },
    { "type": "gstin", "name": "Gstin", "required": false },
    { "type": "cancelled_cheque", "name": "Cancelled Cheque", "required": false },
    { "type": "return_policy", "name": "Return Policy", "required": false }
  ],
  "field_validations": { "...": {} },
  "bank_fields": { "...": {} },
  "tax_fields": { "...": {} }
}
```

- Render one upload control per entry in `required_documents`.
- `required: true` items must be uploaded before submitting. (Currently only
  `pan_card` and `aadhar` are hard-required; the rest are optional but recommended.)
- `type` is the **exact value** you must send as `document_type` in Step 5.
- `field_validations` / `bank_fields` / `tax_fields` describe the country-specific
  text fields (e.g. GSTIN, PAN, IFSC) and their validation rules — render and
  validate accordingly.

### Errors

| Status | Body | When |
|--------|------|------|
| `400` | `{ "error": "Invalid country code", "message": "..." }` | Unsupported country |

See also **`GET /api/auth/countries`** / **`GET /api/merchants/supported-countries`**
for the full supported-country list.

---

## Step 5 — Upload KYC documents

Upload each document the merchant needs. Uploading the **first** document auto-moves
the merchant to `documents_submitted` (submitted for review).

**`POST /api/merchant/documents/upload`** · **Bearer auth (merchant)** · `multipart/form-data`

### Form fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | ✅ | The document (PDF, JPEG, PNG, Excel, or CSV) |
| `document_type` | string | ✅ | One of the `type` values from Step 4 (e.g. `pan_card`) |

Uploading the same `document_type` again **replaces** the previous file and resets
that document's status to `pending`.

### Success

New document → `201 Created`:

```json
{
  "message": "Document uploaded successfully",
  "document": {
    "id": 320,
    "document_type": "pan_card",
    "file_url": "https://cdn.aoinstore.com/merchant-docs/...",
    "status": "pending"
  }
}
```

Replacing an existing document → `200 OK` with `"message": "Document updated successfully"`.

### Errors

| Status | Body | When |
|--------|------|------|
| `400` | `{ "message": "File and document type are required" }` | Missing form field |
| `400` | `{ "message": "Invalid document type. Allowed types: [...]" }` | Bad `document_type` |
| `400` | `{ "message": "<file validation error>" }` | File too large / wrong format |
| `403` | `{ "message": "Unauthorized" }` | Token isn't a merchant |
| `404` | `{ "message": "Merchant profile not found" }` | No profile |
| `500` | `{ "message": "Failed to upload file to storage", "error": "..." }` | S3 failure |

### Other document endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/merchant/documents` | List the merchant's uploaded documents + statuses |
| `GET` | `/api/merchant/documents/<id>` | Single document details |
| `DELETE` | `/api/merchant/documents/<id>` | Remove a document |

---

## Step 6 — Check verification status

Poll this to drive the onboarding progress screen and to detect admin
approval/rejection.

**`GET /api/auth/merchant/profile`** · **Bearer auth (merchant)**

### Success — `200 OK` (abridged)

```json
{
  "id": 51,
  "business_name": "Asha Crafts",
  "business_email": "seller@ashacrafts.com",
  "business_phone": "+91 98765 43210",
  "country_code": "IN",
  "country_name": "India",
  "state_province": "Maharashtra",
  "city": "Pune",
  "postal_code": "411001",
  "gstin": null,
  "pan_number": null,
  "verification_status": "documents_submitted",
  "is_verified": false,
  "verification_notes": null,
  "verification_submitted_at": "2026-06-17T11:00:00",
  "verification_completed_at": null,
  "can_place_premium": false,
  "email": "seller@ashacrafts.com",
  "first_name": "Asha",
  "last_name": "Verma",
  "phone": "+919876543210",
  "documents": {
    "pan_card": {
      "id": 320,
      "type": "pan_card",
      "status": "pending",
      "submitted": true,
      "imageUrl": "https://cdn.aoinstore.com/merchant-docs/...",
      "file_name": "pan.pdf",
      "file_size": 248213,
      "mime_type": "application/pdf",
      "admin_notes": null,
      "verified_at": null
    }
  },
  "country_config": {
    "required_documents": ["pan_card", "aadhar", "..."],
    "field_validations": {},
    "bank_fields": {},
    "tax_fields": {},
    "country_name": "India"
  }
}
```

Key fields for the app:

| Field | Use |
|-------|-----|
| `verification_status` | Drive the progress UI (see status list above) |
| `is_verified` | `true` once approved → unlock the seller dashboard |
| `verification_notes` | Admin's reason on **rejection** — show it to the merchant |
| `documents.<type>.status` | Per-document `pending` / `approved` / `rejected` |
| `documents.<type>.admin_notes` | Per-document rejection reason |

> On `rejected`, let the merchant re-upload the flagged documents (Step 5) — that
> resets them to `pending` and re-submits.

---

## Reference

### Country codes

| Code | Country |
|------|---------|
| `IN` | India |
| `GLOBAL` | All other countries |

### Verification status values

`pending`, `email_verified`, `documents_submitted`, `under_review`, `approved`, `rejected`

### Document status values

`pending`, `approved`, `rejected`

### Document types (`document_type` values)

Send the exact value returned in Step 4's `required_documents[].type`. The full enum
includes (India + Global):

```
business_registration_in, business_registration_global,
pan_card, tax_id_global, gstin, vat_id, sales_tax_reg, import_export_license,
aadhar, voter_id, passport, national_id, driving_license,
business_address_proof_in, business_address_proof_global,
cancelled_cheque, bank_statement, void_cheque, bank_letter,
bank_account_in, bank_account_global,
gst_certificate, vat_certificate, sales_tax_permit,
msme_certificate, small_business_cert, dsc, esign_certificate,
return_policy, shipping_details, product_list, category_list,
brand_approval, brand_authorization, other
```

> Always render from the live `country-config` response rather than hard-coding this
> list — it's country-specific.

### Auth header

All authenticated endpoints expect:

```
Authorization: Bearer <access_token>
```

### Token refresh (session keep-alive)

**`POST /api/auth/refresh`** with `{ "refresh_token": "<token>" }` → returns a new
`access_token`. Use it when the access token expires.

---

## Quick reference — endpoints used in onboarding

| # | Method | Endpoint | Auth |
|---|--------|----------|------|
| 1 | `POST` | `/api/auth/register/merchant` (send `source:"app"`) | — |
| 2 | `POST` | `/api/auth/merchant/verify-email-otp` (app flow) | — |
| 2b | `POST` | `/api/auth/merchant/resend-email-otp` (app flow) | — |
| 2-web | `GET` | `/api/auth/verify-email/<token>` (web link, not used by app) | — |
| 3 | `POST` | `/api/auth/login` (use `business_email`) | — |
| 4 | `GET` | `/api/merchants/country-config/<country_code>` | — |
| 5 | `POST` | `/api/merchant/documents/upload` | Merchant |
| 5b | `GET` | `/api/merchant/documents` | Merchant |
| 6 | `GET` | `/api/auth/merchant/profile` | Merchant |
| — | `POST` | `/api/auth/refresh` | — |
```
