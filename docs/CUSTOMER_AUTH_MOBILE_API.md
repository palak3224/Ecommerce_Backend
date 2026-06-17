# Customer (Buyer) Auth API — Mobile Integration Guide

This document describes the **customer / buyer** authentication surface for the
mobile app: registration, the new **email-OTP verification (app flow)**, login, and
the supporting endpoints. All routes are under `/api/auth`.

> `role: "user"` accounts only. Merchant auth is a separate flow — see
> [MERCHANT_ONBOARDING_MOBILE_API.md](MERCHANT_ONBOARDING_MOBILE_API.md).

---

## Auth options at a glance

A buyer can authenticate **three** ways:

| Method | Register | Login | Password |
|--------|----------|-------|----------|
| **Email + Password** | `POST /register` | `POST /login` | yes (min 8) |
| **Phone + OTP** | `POST /phone/send-otp` → `/phone/verify-signup` | `/phone/send-otp` → `/phone/verify-login` | none |
| **Google OAuth** | `POST /google` (auto-creates) | `POST /google` | none |

This guide focuses on **Email + Password** (with the new app OTP verification) since
that's the flow that changed. Phone and Google are summarized at the end.

---

## Email registration — app uses OTP, web uses a link

Email registration needs the email to be **verified**. There are two verification
styles, selected by the `source` field at registration:

- **Mobile app** sends `"source": "app"` → backend emails a **6-digit OTP** the user
  types into the app. No browser. Identical on Android and iOS.
- **Website** omits `source` → backend emails a **clickable link**.

Everything else (login, profile, etc.) is the same.

> The OTP flow reuses the same engine as merchant onboarding: 6-digit code,
> **10-minute** expiry (config `USER_EMAIL_OTP_EXPIRY_MIN`), single-use, throttled
> resend.

---

## Step 1 — Register (app flow)

**`POST /api/auth/register`** · no auth

### Request body

```json
{
  "email": "buyer@example.com",
  "password": "StrongPass123",
  "first_name": "Bob",
  "last_name": "Buyer",
  "phone": "+919876543210",
  "source": "app"
}
```

| Field | Required | Rules |
|-------|----------|-------|
| `email` | ✅ | valid email — becomes the login email |
| `password` | ✅ | min 8 chars |
| `first_name`, `last_name` | ✅ | string |
| `phone` | ❌ | optional |
| `source` | ❌ | `"app"` (OTP) or `"web"` (link, default). **App must send `"app"`.** |

### Success — `201 Created`

```json
{
  "message": "User registered successfully. Please check your email for the verification code.",
  "user_id": 42,
  "verification_method": "otp"
}
```

> **`verification_method`** tells the app what to do next: `"otp"` → go to Step 2;
> `"link"` → the user verifies via the emailed link (web only).
>
> **Dev/QA only:** when `DEV_OTP_BYPASS` is enabled the response also contains
> `"dev_otp": "483920"` so testers can verify without a real inbox. **Never present
> in production.**

### Errors

| Status | Body | When |
|--------|------|------|
| `400` | `{ "error": "Validation error", "details": { ... } }` | Validation failed (e.g. password < 8, bad `source`, unknown field) |
| `409` | `{ "error": "Email already registered" }` | Email in use |
| `500` | `{ "error": "Registration failed" }` | Server error |

> ⚠️ **Unknown JSON fields are rejected with 400.** Only send the documented fields.

---

## Step 2 — Verify email with OTP (app flow)

**`POST /api/auth/verify-email-otp`** · no auth

### Request body

```json
{
  "email": "buyer@example.com",
  "otp": "483920"
}
```

| Field | Required | Rules |
|-------|----------|-------|
| `email` | ✅ | the email used at registration |
| `otp` | ✅ | exactly 6 digits |

### Success — `200 OK`

The buyer is verified **and logged in** — tokens are returned so the app can go
straight into the authenticated experience without a separate login call.

```json
{
  "message": "Email verified successfully",
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": {
    "id": 42,
    "email": "buyer@example.com",
    "first_name": "Bob",
    "last_name": "Buyer",
    "role": "user",
    "is_email_verified": true
  }
}
```

> Store `access_token` / `refresh_token` here. Use the access token as
> `Authorization: Bearer <token>` on all authenticated calls.

### Errors

| Status | Body | When |
|--------|------|------|
| `400` | `{ "error": "Validation error", "details": { ... } }` | `otp` not 6 chars / missing field |
| `400` | `{ "error": "Invalid or expired OTP" }` | Wrong or expired code |
| `403` | `{ "error": "This verification method is only for customer accounts." }` | Email belongs to a merchant — use the merchant endpoint |
| `500` | `{ "error": "Email verification failed" }` | Server error |

> **Idempotent:** if the account is already verified, returns `200` with a fresh
> session — a retried request is safe.

### Resend the OTP

**`POST /api/auth/resend-email-otp`** · no auth

```json
{ "email": "buyer@example.com" }
```

Always returns a generic message (no email enumeration). Throttled:

| Status | Body | When |
|--------|------|------|
| `200` | `{ "message": "If your email is registered and not verified, a new code has been sent." }` | Sent (or generic no-op) |
| `200` | `{ "message": "Your email address is already verified." }` | Nothing to do |
| `429` | `{ "error_code": "RATE_LIMIT_APPLIED", "message": "...", "retry_after": 30 }` | Requested again within 30s |
| `429` | `{ "error_code": "RATE_LIMIT_EXCEEDED", ... }` | Daily cap reached |

> Each resend invalidates any previous unused code — only the latest OTP works, and
> a new one resets the 10-minute expiry.

---

## Step 3 — Login

**`POST /api/auth/login`** · no auth

```json
{
  "email": "buyer@example.com",
  "password": "StrongPass123"
}
```

### Success — `200 OK`

```json
{
  "message": "Login successful",
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": {
    "id": 42,
    "email": "buyer@example.com",
    "first_name": "Bob",
    "last_name": "Buyer",
    "role": "user",
    "is_email_verified": true
  }
}
```

### Errors

| Status | Body | When |
|--------|------|------|
| `401` | `{ "error": "Invalid email or password" }` | Bad credentials |
| `403` | `{ "error_code": "EMAIL_NOT_VERIFIED", "message": "...", "email": "..." }` | Email not verified → send user to Step 2 (or resend) |
| `403` | `{ "error": "Account is disabled" }` | Account disabled |
| `400` | `{ "error": "Validation error", "details": { ... } }` | Missing fields |

> Handle `error_code: "EMAIL_NOT_VERIFIED"` specially: if the user registered via the
> app, route them to the **OTP** screen (resend with `/resend-email-otp`).

---

## Alternative methods (summary)

### Phone + OTP (buyers only)

```
POST /api/auth/phone/send-otp        { "phone": "+919876543210" }   // E.164
   → 200 { "message": "OTP sent successfully", "expires_in": 600 }   // dev_otp under DEV_OTP_BYPASS

# New phone → sign up:
POST /api/auth/phone/verify-signup   { phone, otp, first_name, last_name }
   → 201 { access_token, refresh_token, user{...} }

# Existing phone → log in:
POST /api/auth/phone/verify-login    { phone, otp }
   → 200 { access_token, refresh_token, user{...} }
```

- OTP is 6 digits, **10-minute** expiry, delivered by SMS (Twilio).
- Phone-signup creates a buyer with a **temporary email** (`phone_<num>@temp.aoin.com`)
  and no password — prompt them to add a real email/password later if needed.
- Merchants cannot use phone auth → `403`.
- Unregistered phone on `verify-login` → `404`.

### Google OAuth

```
POST /api/auth/google   { "id_token": "<google_id_token>" }
   → 200 { access_token, refresh_token, user{...} }
```

- Auto-creates the account on first sign-in (email pre-verified by Google).
- Invalid token → `401`; email already registered with another provider → `409`.

---

## Supporting endpoints

| Method | Endpoint | Auth | Purpose |
|--------|----------|------|---------|
| `GET` | `/api/auth/me` | Bearer | Current user info |
| `POST` | `/api/auth/refresh` | — | New access token from `{ "refresh_token": "..." }` |
| `POST` | `/api/auth/logout` | Bearer | Revoke refresh token |
| `POST` | `/api/auth/password/reset-request` | — | `{ "email": "..." }` → reset link (generic `200`) |
| `POST` | `/api/auth/password/reset` | — | `{ "token": "...", "new_password": "..." }` → resets + logs out all sessions |

> Password reset works only for password (LOCAL) accounts. Google/phone-only users
> get `400 "Please use your social login provider..."`.

---

## Frontend integration notes

1. **Pick the email-OTP path on mobile:** always send `"source": "app"` at
   registration, then drive the OTP screen via `verify-email-otp` / `resend-email-otp`.
   No browser/deep-link handling required.
2. **`verification_method` is your switch** — branch the post-register UI on it.
3. **`EMAIL_NOT_VERIFIED` on login** → route app users to the OTP screen and call
   `resend-email-otp` to get a fresh code.
4. **Idempotency:** re-calling `verify-email-otp` after success returns `200` — safe
   to retry on flaky networks.
5. **Throttling:** treat `429` on resend as "wait" (`retry_after` seconds), not an error.
6. **Only send documented fields** — the API rejects unknown JSON keys with `400`.

---

## Quick reference — endpoints

| Method | Endpoint | Auth | Notes |
|--------|----------|------|-------|
| `POST` | `/api/auth/register` (send `source:"app"`) | — | Email register → OTP |
| `POST` | `/api/auth/verify-email-otp` | — | App email verification |
| `POST` | `/api/auth/resend-email-otp` | — | Resend code (throttled) |
| `POST` | `/api/auth/login` | — | Email + password |
| `POST` | `/api/auth/phone/send-otp` | — | Phone OTP (signup/login) |
| `POST` | `/api/auth/phone/verify-signup` | — | Phone signup |
| `POST` | `/api/auth/phone/verify-login` | — | Phone login |
| `POST` | `/api/auth/google` | — | Google OAuth |
| `GET` | `/api/auth/me` | Bearer | Current user |
| `POST` | `/api/auth/refresh` | — | Refresh token |
| `POST` | `/api/auth/logout` | Bearer | Logout |
| `POST` | `/api/auth/password/reset-request` | — | Start reset |
| `POST` | `/api/auth/password/reset` | — | Complete reset |

---
