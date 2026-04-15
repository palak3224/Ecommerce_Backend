# User account deletion — guide for frontend developers

This document describes the **user/buyer-initiated account closure** flow (grace period, then soft close). Use it to wire **web**, **React Native**, or any client that calls the user APIs with a JWT.

---

## Base URL and auth

- **Prefix:** `{API_BASE_URL}/api/users`
- **Auth:** `Authorization: Bearer <access_token>` on every call below.
- **Role:** The token identity must be a **user** (`user_role_required`). Merchant/admin tokens receive **403**.
- **CORS:** Routes support `OPTIONS` (preflight returns **204** with empty body).

---

## Related endpoint: who needs a password?

If your frontend already has a “user info” endpoint that exposes `has_password`, use it to decide whether to prompt for password.

Backend behavior:
- If `users.password_hash` exists, `POST .../deletion-request` requires `password`.
- If not (OAuth-only account), omit `password` or send `{}`.

---

## 1. Deletion status (poll + initial load)

**`GET /api/users/account/deletion-status`**

### Success **200** — response body

| Field | Type | Description |
|------|------|-------------|
| `status` | `"none"` \| `"pending"` \| `"closed"` | UI state driver. |
| `account_deletion_requested_at` | `string \| null` | ISO 8601 timestamp, or `null`. |
| `account_deletion_effective_at` | `string \| null` | ISO 8601 when grace ends, or `null`. |
| `account_deleted_at` | `string \| null` | Set when fully closed (after job runs). |
| `grace_hours` | `number` | Server-configured grace length (default **24**). |
| `message` | `string` | Human-readable status copy. |

---

## 2. Request deletion (start grace period)

**`POST /api/users/account/deletion-request`**

Body (JSON): `{ "password": "..." }` only when required.

---

## 3. Cancel deletion (within grace window)

**`POST /api/users/account/deletion-cancel`**

---

## 4. After the account is closed (global client behaviour)

Finalization sets **`users.is_active = false`** and revokes refresh tokens.

- Any user API protected by `user_role_required` / `role_required` returns **403** with `{ "error": "Account is disabled" }`.
- **Action:** clear tokens, run logout, redirect to sign-in, and show “Account closed”.

