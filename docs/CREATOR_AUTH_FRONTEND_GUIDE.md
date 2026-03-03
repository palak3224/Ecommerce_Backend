# Creator Auth — Frontend Integration Guide

This guide is for **frontend developers** integrating the **Creator (influencer) signup and login** flow. It documents the APIs, request/response shapes, and how to wire them in the UI.

---

## 1. Overview

**Creator signup (new users)** is a 3-step flow:

1. **Step 1:** User enters **name**, **email**, and **phone** → backend sends **OTP** to the phone.
2. **Step 2 (optional):** User can request **Resend OTP** (rate limited to once per 60 seconds).
3. **Step 3:** User enters **OTP** → backend creates the creator account and returns **JWT tokens** and **user** → redirect to **category selection** (5 categories) to complete onboarding.

**Creator login (returning users)** uses the existing **phone OTP** flow: send OTP to phone, then verify OTP to get tokens. Same as customer phone login; the response includes `role: "creator"` so you can route to the Creator dashboard.

---

## 2. Base URL & Headers

| Item | Value |
|------|--------|
| **Base URL** | Your backend base (e.g. `https://api.aoinstore.com` or `http://localhost:5000`) |
| **Content-Type** | `application/json` for all requests below |
| **Auth (after login)** | `Authorization: Bearer <access_token>` for protected routes (e.g. onboarding) |

Use the same base URL and CORS/credentials setup as the rest of your app (e.g. `credentials: 'include'` if using cookies; or send the Bearer token in the header after signup/verify).

---

## 2.1 Standard error shape (all creator auth APIs)

Every error response from the creator signup/verify endpoints uses this shape:

```json
{
  "error": "Human-readable message to show the user",
  "code": "MACHINE_READABLE_CODE"
}
```

Optional field (e.g. for validation or debug):

- **`detail`** — extra info: `{ "field": "phone" }`, `{ "retry_after_seconds": 45 }`, or (when backend is in DEBUG) a technical message.

**Error codes:**

| Code | HTTP | Meaning | Suggested UI |
|------|------|---------|--------------|
| `VALIDATION_ERROR` | 400 | Invalid/missing field (check `detail.field`) | Show message under the field. |
| `SESSION_EXPIRED` | 400 | No pending signup for this phone; user must re-enter details. | Redirect to step 1 (name, email, phone). |
| `OTP_INVALID` | 400 | Wrong or expired OTP. | “Invalid or expired code. Try again or resend.” |
| `OTP_ALREADY_USED` | 400 | OTP was already used (e.g. double submit). | “This code was already used. Request a new OTP.” |
| `RATE_LIMITED` | 429 | Resend OTP too soon (check `detail.retry_after_seconds`). | Disable resend; show countdown. |
| `ALREADY_REGISTERED` | 409 | Phone or email already registered. | “Already registered. Try logging in.” |
| `OTP_SEND_FAILED` | 500 | Could not send SMS. | “Could not send OTP. Check number and try again.” |
| `CREATOR_SIGNUP_FAILED` | 500 | Account creation failed (server/config issue). | Show `error`; if `detail` is present (e.g. in DEBUG), you can show or log it. |
| `SERVER_ERROR` | 500 | Generic server error. | “Something went wrong. Please try again.” |

**Example:** Show the user `response.error`; use `response.code` for specific behaviour (e.g. redirect on `SESSION_EXPIRED`, countdown on `RATE_LIMITED`).

---

## 3. Creator Signup APIs

All three endpoints are under **`/api/auth/creator/`** and do **not** require a token.

---

### 3.1 Step 1 — Request OTP (send signup details)

**Purpose:** Submit name, email, and phone. Backend sends a 6-digit OTP to the phone. Store the phone (and optionally name/email) in your app state for the next steps.

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/auth/creator/signup-request` | No |

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| first_name | string | Yes | 1–100 characters. |
| last_name | string | Yes | 1–100 characters. |
| email | string | Yes | Valid, unique email. |
| phone | string | Yes | E.164 recommended (e.g. `+919876543210`). |

**Example request:**
```json
{
  "first_name": "Jane",
  "last_name": "Creator",
  "email": "jane.creator@example.com",
  "phone": "+919876543210"
}
```

**Success (200):**
```json
{
  "message": "OTP sent to your phone.",
  "expires_in": 600
}
```
- Show a screen asking the user to enter the 6-digit OTP.
- Keep `phone` (and optionally name/email) in state for **Verify OTP** and for **Resend OTP**.

**Error responses:**

| Status | Body | When | What to show |
|--------|------|------|----------------|
| 400 | `{ "error": "Invalid phone number format. Use E.164 (e.g. +919876543210)." }` | Invalid phone | Ask user to fix phone format. |
| 400 | `{ "error": "First name and last name are required." }` | Missing name | Show validation message. |
| 400 | `{ "error": "Valid email is required." }` | Invalid email | Show validation message. |
| 409 | `{ "error": "This phone number is already registered." }` | Phone exists | “This number is already registered. Try logging in.” |
| 409 | `{ "error": "This email is already registered." }` | Email exists | “This email is already registered.” |
| 500 | `{ "error": "Failed to send OTP." }` or Twilio message | SMS failed | “Could not send OTP. Check number and try again.” |

---

### 3.2 Resend OTP

**Purpose:** Send the OTP again to the same phone. Use when the user didn’t receive the SMS or it expired. **Rate limited:** one resend per **60 seconds** per phone.

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/auth/creator/resend-otp` | No |

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| phone | string | Yes | Same phone used in signup-request. |

**Example request:**
```json
{
  "phone": "+919876543210"
}
```

**Success (200):**
```json
{
  "message": "OTP sent again.",
  "expires_in": 600
}
```
- Optionally show a short “New OTP sent” toast.
- Disable “Resend OTP” for 60 seconds and show a countdown (e.g. “Resend in 45s”).

**Error responses:**

| Status | Body | When | What to do |
|--------|------|------|------------|
| 400 | `{ "error": "Invalid phone number format." }` | Bad phone | Fix phone format. |
| 400 | `{ "error": "Session expired. Please enter your details again and request a new OTP." }` | No pending signup for this phone (or expired) | Redirect user back to Step 1 (name, email, phone). |
| 429 | `{ "error": "Please wait 60 seconds before requesting another OTP." }` (or with actual `wait` seconds) | Too soon since last OTP | Show countdown; disable resend until cooldown over. |
| 500 | `{ "error": "Failed to resend OTP." }` | Server/SMS error | Retry or show “Try again later.” |

---

### 3.3 Step 2 — Verify OTP (create account)

**Purpose:** User enters the 6-digit OTP. Backend verifies it, creates the **creator** account (no password), and returns **JWT tokens** and **user**. After this, redirect to **category selection** (5 categories) for onboarding.

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/auth/creator/verify-otp` | No |

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| phone | string | Yes | Same phone used in signup-request. |
| otp | string | Yes | Exactly 6 digits. |

**Example request:**
```json
{
  "phone": "+919876543210",
  "otp": "123456"
}
```

**Success (201):**
```json
{
  "message": "Account created. Complete your profile by selecting 5 categories.",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJ...",
  "expires_in": 3600,
  "user": {
    "id": 42,
    "email": "jane.creator@example.com",
    "phone": "+919876543210",
    "first_name": "Jane",
    "last_name": "Creator",
    "role": "creator",
    "is_phone_verified": true
  }
}
```
- Store **access_token** (and optionally **refresh_token**) (e.g. memory, secure storage, or cookie).
- Set **Authorization: Bearer &lt;access_token&gt;** for all subsequent creator APIs.
- Redirect to **category selection** screen (onboarding: select 5 categories). The onboarding API will be **POST /api/creator/onboarding** (see main API spec when available).

**Error responses:**

| Status | Body | When | What to show |
|--------|------|------|----------------|
| 400 | `{ "error": "Invalid phone number format." }` | Bad phone | Re-enter phone. |
| 400 | `{ "error": "Invalid or expired OTP." }` | Wrong OTP or expired | “Wrong or expired code. Try again or resend OTP.” |
| 400 | `{ "error": "Session expired. Please enter your details again." }` | No pending signup for this phone | Redirect to Step 1. |
| 409 | `{ "error": "This phone or email is already registered." }` | Race (e.g. registered meanwhile) | “Already registered. Try logging in.” |
| 500 | `{ "error": "Failed to create account." }` | Server error | “Something went wrong. Try again.” |

---

## 4. Creator Login (returning users)

Creators who signed up with **phone + OTP** have **no password**. They log in with the **same phone OTP** flow as customers:

1. **POST** `/api/auth/phone/send-otp`  
   Body: `{ "phone": "+919876543210" }`  
   → Backend sends OTP (for login if user exists).

2. **POST** `/api/auth/phone/verify-login`  
   Body: `{ "phone": "+919876543210", "otp": "123456" }`  
   → Backend returns `access_token`, `refresh_token`, and **user** with **`role: "creator"`**.

Use **`user.role === "creator"`** to redirect to the Creator dashboard (or onboarding if they haven’t completed categories yet).

---

## 5. Frontend flow summary

```
[Creator Signup screen]
  → User enters: First name, Last name, Email, Phone
  → POST /api/auth/creator/signup-request
  → On 200: Navigate to [Enter OTP] screen, store phone (and name/email if needed)

[Enter OTP screen]
  → "Resend OTP" button → POST /api/auth/creator/resend-otp (disable for 60s after send/resend)
  → User enters 6-digit OTP → POST /api/auth/creator/verify-otp
  → On 201: Store access_token (and refresh_token), store user
  → Redirect to [Select 5 categories] (onboarding)

[Select 5 categories]
  → POST /api/auth/creator/onboarding (with Bearer token) when that API is ready
  → Then redirect to Creator dashboard
```

**Creator login:**  
Use **POST /api/auth/phone/send-otp** then **POST /api/auth/phone/verify-login**. If `user.role === "creator"`, send them to Creator dashboard (or onboarding if not done).

---

## 6. Example: cURL

Replace `BASE` with your backend base URL (e.g. `https://api.aoinstore.com` or `http://localhost:5000`).

**Step 1 — Request OTP**
```bash
curl -X POST "${BASE}/api/auth/creator/signup-request" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jane",
    "last_name": "Creator",
    "email": "jane.creator@example.com",
    "phone": "+919876543210"
  }'
```

**Resend OTP**
```bash
curl -X POST "${BASE}/api/auth/creator/resend-otp" \
  -H "Content-Type: application/json" \
  -d '{"phone": "+919876543210"}'
```

**Step 2 — Verify OTP (create account, get tokens)**
```bash
curl -X POST "${BASE}/api/auth/creator/verify-otp" \
  -H "Content-Type: application/json" \
  -d '{"phone": "+919876543210", "otp": "123456"}'
```

**Creator login (returning user) — Send OTP**
```bash
curl -X POST "${BASE}/api/auth/phone/send-otp" \
  -H "Content-Type: application/json" \
  -d '{"phone": "+919876543210"}'
```

**Creator login — Verify OTP and get tokens**
```bash
curl -X POST "${BASE}/api/auth/phone/verify-login" \
  -H "Content-Type: application/json" \
  -d '{"phone": "+919876543210", "otp": "123456"}'
```

---

## 7. Validation tips (frontend)

- **Phone:** Prefer E.164 (e.g. `+919876543210`). Add country code if you have a picker.
- **OTP:** Exactly 6 digits; allow digits only in the input.
- **Resend:** Disable the resend button for 60 seconds after the last successful send/resend; show a countdown to avoid 429.

### Avoiding "Invalid or expired OTP" when the code is correct

1. **Use the same phone value for verify as for signup-request**  
   Store the **exact** string you sent in `signup-request` (e.g. `+919876543210`) and send that same string in `verify-otp`. If you send a different format (e.g. without `+` or with different spacing), the backend won’t find the OTP.

2. **Send OTP as a 6-digit string**  
   e.g. `"otp": "123456"`. The backend accepts digits-only and normalizes; sending as a string avoids any number vs string mismatch.

3. **Don’t double-submit**  
   After the user taps “Verify”, disable the button until the response is back. If the request is sent twice, the first one consumes the OTP and the second will get **"OTP already used. Please request a new OTP."**

4. **Use the latest OTP**  
   If the user clicked “Resend OTP”, they must enter the **new** code. The previous code is no longer valid.

---

## 8. Related docs

- **Full API spec (all Creator APIs):** [CREATOR_MODULE_API_SPEC.md](./CREATOR_MODULE_API_SPEC.md)  
- **Product/flow context:** [CREATOR_MODULE_PRD.md](./CREATOR_MODULE_PRD.md)

---

*Document version: 1.0. Covers creator signup (signup-request, resend-otp, verify-otp) and login via existing phone OTP.*
