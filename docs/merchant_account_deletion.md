# Merchant account deletion — guide for frontend developers

This document describes the **merchant-initiated account closure** flow (grace period, then soft close). Use it to wire **web**, **React Native**, or any client that calls the merchant API with a JWT.

---

## Base URL and auth

- **Prefix:** `{API_BASE_URL}/api/merchant-dashboard`
- **Auth:** `Authorization: Bearer <access_token>` on every call below.
- **Role:** The token identity must be a **merchant** user (`merchant_role_required`). Customer or admin tokens receive **403**.
- **CORS:** Routes support `OPTIONS` (preflight returns **204** with empty body).

Replace `{API_BASE_URL}` with your app config (e.g. `import.meta.env.VITE_API_BASE_URL` on web).

---

## Related endpoint: who needs a password?

Before showing the “confirm delete” step, call existing user info so you know whether the backend will require a password:

**`GET /api/merchant-dashboard/user-info`**

Relevant field:

| Field | Type | Meaning |
|-------|------|---------|
| `has_password` | `boolean` | If `true`, `POST .../deletion-request` **must** include `password` in the JSON body. If `false` (e.g. OAuth-only account), send `{}` or omit `password`. |

---

## 1. Deletion status (poll + initial load)

**`GET /api/merchant-dashboard/account/deletion-status`**

Use on screen load and optionally on an interval (e.g. every 60s) while `status === "pending"`, and after request/cancel completes.

### Success **200** — response body

All keys are always present unless noted.

| Field | Type | Description |
|-------|------|-------------|
| `status` | `"none"` \| `"pending"` \| `"closed"` | UI state driver. |
| `account_deletion_requested_at` | `string \| null` | ISO 8601 timestamp when deletion was requested, or `null`. |
| `account_deletion_effective_at` | `string \| null` | ISO 8601 when the grace period ends (cancel deadline). `null` if not scheduled. |
| `account_deleted_at` | `string \| null` | Set when the account is **fully closed** (after the job runs). |
| `grace_hours` | `number` | Server-configured grace length (default **24**). Display copy like “You have {{grace_hours}} hours to cancel.” |
| `message` | `string` | Human-readable status for banners or subtitles. |

**`status` meanings for UI**

| `status` | What to show |
|----------|----------------|
| `none` | Normal merchant; show “Delete / close account” entry point if you support deletion. |
| `pending` | Deletion scheduled. Show **countdown** to `account_deletion_effective_at`, **Cancel deletion** button, and `message`. Merchant can still use the app until finalization. |
| `closed` | Account closed: user will get **403** on most merchant APIs (`"Account is disabled"`). Clear tokens, redirect to sign-in, show “Account closed” if they land on settings. |

### Timestamps and countdowns

- Prefer **`account_deletion_effective_at`** for countdown: `remainingMs = new Date(account_deletion_effective_at).getTime() - Date.now()`.
- Values are ISO strings; treat them as UTC-safe when parsing (`Date` handles `...Z` and many offset forms).
- After the effective time passes, `status` may stay `"pending"` briefly with `message` like “Account deletion is being finalized.” until the background job runs (default job interval **10 minutes**). Keep polling `deletion-status` or show “Finalizing…” instead of a negative timer.

### Error **404**

```json
{ "error": "Merchant profile not found" }
```

---

## 2. Request deletion (start grace period)

**`POST /api/merchant-dashboard/account/deletion-request`**

**Headers:** `Authorization`, `Content-Type: application/json`

**Body (JSON)**

| Field | Required | Description |
|-------|----------|-------------|
| `password` | Only if `has_password === true` | Current account password. |

Examples:

```json
{}
```

```json
{ "password": "currentPlaintextPassword" }
```

### Success **200** — new request

```json
{
  "status": "pending",
  "account_deletion_requested_at": "2026-04-13T12:00:00",
  "account_deletion_effective_at": "2026-04-14T12:00:00",
  "grace_hours": 24,
  "message": "Account deletion scheduled. You may cancel within 24 hours."
}
```

### Success **200** — idempotent (already pending)

If the user already requested deletion, the same **`account_deletion_effective_at`** is returned (no duplicate schedule):

```json
{
  "status": "pending",
  "account_deletion_effective_at": "2026-04-14T12:00:00",
  "message": "Deletion was already requested."
}
```

### Errors

| HTTP | Body | When |
|------|------|------|
| **400** | `{ "error": "Password is required to delete this account" }` | `has_password` but body missing `password`. |
| **403** | `{ "error": "Invalid password" }` | Wrong password. |
| **404** | `{ "error": "Merchant profile not found" }` | No merchant profile for JWT user. |
| **410** | `{ "error": "Account is already closed" }` | `account_deleted_at` is set; treat like logged-out / closed account. |

---

## 3. Cancel deletion (within grace window)

**`POST /api/merchant-dashboard/account/deletion-cancel`**

**Body:** empty JSON `{}` or no body.

### Success **200**

```json
{
  "status": "none",
  "message": "Account deletion has been cancelled."
}
```

### Errors

| HTTP | Body |
|------|------|
| **400** | `{ "error": "No pending deletion to cancel" }` |
| **404** | `{ "error": "Merchant profile not found" }` |
| **410** | `{ "error": "Account is already closed" }` |

After success, call **`deletion-status`** again (or assume `status === "none"`).

---

## 4. After the account is closed (global client behaviour)

When finalization runs, the backend sets **`users.is_active = false`** and revokes refresh tokens.

- Any merchant API using the shared **`role_required`** / **`merchant_role_required`** guard returns **403** with body like **`{ "error": "Account is disabled" }`** (same idea as login).
- **Action:** clear `access_token` / `refresh_token` from storage, call your **logout** flow, redirect to merchant sign-in, and optionally show a message that the account was closed.

You do not need a separate “logout” API for closure; tokens become unusable for refresh, and access tokens are rejected once inactive.

---

## 5. Reference implementation (web)

The merchant **React** dashboard implements this under:

- **Page:** [`Ecommerce/src/pages/business/Settings.tsx`](../../Ecommerce/src/pages/business/Settings.tsx) (Account tab — “Close merchant account”).
- **Patterns:** modal confirmation, password field when `userInfo.has_password`, countdown from `account_deletion_effective_at`, cancel button, `fetchDeletionStatus` with `useCallback` + polling while pending.

Privacy / retention copy for users:

- **In app:** link to **`/privacy-policy`** (or your deployed privacy URL).
- **Content:** merchant closure and legal retention are described in the privacy policy (sections updated for merchant account closure).

---

## 6. Minimal integration checklist (frontend)

1. On merchant settings (or profile), **`GET user-info`** → store `has_password`.
2. On mount (and when opening the screen), **`GET deletion-status`** → drive `none` / `pending` / `closed` UI.
3. **Delete flow:** confirm modal → if `has_password`, collect password → **`POST deletion-request`** with body as above.
4. If **`pending`:** show countdown + **`POST deletion-cancel`**.
5. On **403** `"Account is disabled"` from any merchant call → logout + redirect.
6. For **App Store / review:** document the grace period in review notes; use a staging env with lower `ACCOUNT_DELETION_GRACE_HOURS` if you need a faster demo.

---

## 7. Backend-only reference (ops / config)

| Environment variable | Default | Purpose |
|----------------------|---------|---------|
| `ACCOUNT_DELETION_GRACE_HOURS` | `24` | Grace period length. |
| `MERCHANT_ACCOUNT_DELETION_JOB_ENABLED` | `true` | Disable finalizer job if `false`. |
| `MERCHANT_ACCOUNT_DELETION_JOB_INTERVAL_MINUTES` | `10` | How often due accounts are finalized. |

**Database:** `merchant_profiles.account_deletion_requested_at`, `account_deletion_effective_at`, `account_deleted_at` — see `migrations/sql/008_merchant_account_deletion.sql` and `init_db.run_migration_008_merchant_account_deletion()`.

**Service logic:** [`Ecommerce_Backend/services/merchant_account_deletion_service.py`](../services/merchant_account_deletion_service.py)

**Routes:** [`Ecommerce_Backend/routes/merchant_account_deletion_routes.py`](../routes/merchant_account_deletion_routes.py)

---

## 8. Example `fetch` calls (web)

```ts
const headers = {
  Authorization: `Bearer ${accessToken}`,
  'Content-Type': 'application/json',
};

// Status
await fetch(`${API_BASE_URL}/api/merchant-dashboard/account/deletion-status`, {
  headers: { Authorization: headers.Authorization },
});

// Request (with password)
await fetch(`${API_BASE_URL}/api/merchant-dashboard/account/deletion-request`, {
  method: 'POST',
  headers,
  body: JSON.stringify({ password: '...' }),
});

// Request (no local password)
await fetch(`${API_BASE_URL}/api/merchant-dashboard/account/deletion-request`, {
  method: 'POST',
  headers,
  body: JSON.stringify({}),
});

// Cancel
await fetch(`${API_BASE_URL}/api/merchant-dashboard/account/deletion-cancel`, {
  method: 'POST',
  headers: { Authorization: headers.Authorization },
});
```

---

## 9. Optional `curl` (manual QA)

```bash
export API=https://your-api.example.com
export TOKEN=eyJ...

curl -sS "$API/api/merchant-dashboard/account/deletion-status" \
  -H "Authorization: Bearer $TOKEN"

curl -sS -X POST "$API/api/merchant-dashboard/account/deletion-request" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"password":"yourPassword"}'

curl -sS -X POST "$API/api/merchant-dashboard/account/deletion-cancel" \
  -H "Authorization: Bearer $TOKEN"
```
