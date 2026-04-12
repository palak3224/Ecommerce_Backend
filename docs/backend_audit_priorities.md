# Backend audit — task priority and risk tiers

This document classifies work from [backend_audit.md](./backend_audit.md) by **risk of breakage** when implemented. Tiers describe **production and integration risk**, not business importance.

**How to read it**

- **Tier 1** — Safest first; mostly additive or verification.
- **Tier 5** — Highest blast radius (data loss, full outage, payment flows); needs runbooks and staging.

**Recommended order:** complete lower tiers (with tests) before touching secrets, keys, CVV, and fail-fast production config.

---

## Tier 1 — Very low break risk

Mostly additive; runtime behavior unchanged until you deliberately wire or enforce something.

| Task | Notes |
|------|--------|
| Add **pytest** and a **`tests/`** directory | Start with smoke tests (`create_app()`, health). |
| **`python -m compileall -q .`** in CI | Syntax-only; no behavior change. **Done:** monorepo workflow [`.github/workflows/ecommerce-backend-compileall.yml`](../../.github/workflows/ecommerce-backend-compileall.yml) (excludes `venv`/`.venv`). Local: `cd Ecommerce_Backend && python -m compileall -q -x '/(\.venv|venv|__pycache__)/' .` |
| **Structured logging** (keep existing behavior; replace `print` gradually) | **Partial (§11):** `common/logging_config.py` + `configure_app_logging` in `create_app`; `LOG_LEVEL`, `LOG_FORMAT=json`; `print` removed in `s3_service.upload_product_media`, `product_controller`, `product_routes`, `shop_cart`, creator OTP path. Remaining: chatbot/API error sanitization, other `print` (e.g. `merchant_routes` STAGE logs, CLI). |
| **Document** cache/Redis reality (null cache, residual Redis code paths) | **Partial (§9):** [`docs/backend_cache_redis.md`](./backend_cache_redis.md) + comments in `common/cache.py`, `config.py`, `app.py`, `translate_service.py`. Remaining: translate `None`-Redis guard / disable paths / intentional re-enable. |
| **PR secret scanning** (gitleaks, detect-secrets) | Blocks bad commits; no app behavior change. |
| **Remove duplicate repo trees** | **Only** after proving one canonical tree (grep imports). If anything imports the stale copy, treat as Tier 3. |

---

## Tier 2 — Low–medium risk

Often breaks **CI or PR workflow** until fixed; production risk is lower if you stage config changes.

| Task | Notes |
|------|--------|
| **ruff**, **black**, **import sorting** on PR | Wide diffs and merge noise; runtime usually unchanged if mechanical. |
| **deptry** / explicit declaration of direct imports | CI fails until requirements match imports. |
| **Pin dependencies** (`requirements.in` → locked `requirements.txt`) | Can expose version drift; resolve in a dedicated branch until green. |
| **Split requirement files** (API / dev / AI) | Update **all** install paths (Docker, scripts, docs) in the same change. |
| **ALLOWED_ORIGINS and `/docs` from env** — *transition* | First: read env **with** temporary fallback to current in-code list. Removing fallbacks moves this to Tier 4. |
| **Sanitize client-facing errors** (no tracebacks in JSON) | Rare clients parsing error strings may break. |
| **One MySQL driver / one WSGI strategy** | Must align ops entrypoints (gunicorn vs waitress, etc.). |

---

## Tier 3 — Medium risk

Requires **staging + smoke tests**; mistakes cause subtle 404s, 500s, or duplicate/missed background work.

| Task | Notes |
|------|--------|
| **Split `app.py`** (factory, blueprints, middleware, errors) | Watch import cycles and registration order. |
| **Split oversized route/controller modules** | Easy to miss a route or decorator. |
| **Move logic into services / use-cases** | Behavior drift without tests on edge cases. |
| **Move `BackgroundScheduler` out of web process** | Exactly **one** worker/cron must own each job (no duplicates, no gaps). |
| **Redis / translation guards** | May disable or alter optional features; decide product behavior explicitly. |
| **Readiness probes / graceful shutdown** | Wrong hooks confuse load balancers and rolling deploys. |
| **Isolate chatbot / AI runtime from main Flask API** | URLs, CORS, env, and deployment topology must stay consistent. |

---

## Tier 4 — High risk

Data posture, deploy parity, or integrations; mistakes cause **outages**, **payment/auth failures**, or **CORS-wide** breakage.

| Task | Notes |
|------|--------|
| **Remove secret/credential fallbacks** | Misconfigured env → app refuses to start (intended but impactful). |
| **`ProductionConfig` fail-fast** when required vars missing | **Staging must mirror prod** secret shape before rollout. |
| **Secrets in AWS Secrets Manager / SSM only** | IAM, rotation, and wrong version → auth/payment/integration failures. |
| **Stable `CARD_ENCRYPTION_KEY` from external store; no generate-on-init** | If data was encrypted with ephemeral keys, plan **re-encrypt** or accept unreadable data. |
| **Remove CVV persistence** | DB migration + API + often **frontend**; coordinate release. |
| **Tokenized payment flows** | Larger product/compliance surface; highest coordination. |
| **CORS allowlist env-only with no in-code fallback** | Typo → all browser clients fail CORS. |
| **Disable or protect `/docs` in production** | Breaks internal workflows that relied on prod Swagger. |

---

## Tier 5 — Highest risk if rushed

Incident-scale impact: **irreversible data issues** or **total production outage** without careful sequencing.

| Task | Why |
|------|-----|
| **Encryption key rotation / change** without dual-key decrypt and re-encrypt | Encrypted columns can become **permanently unreadable**. |
| **CVV removal + schema** without backup and rollback | Failed migration can leave inconsistent payment data. |
| **Fail-fast production deploy** before secrets exist in the new store | **Complete outage** until every required value is present. |

---

## Suggested implementation sequence

1. **Tier 1** — Tests, compileall, secret scanning; verify duplicate-tree usage before deleting duplicates.
2. **Tier 2** — Lint/format, dependency pinning and split manifests; update install/deploy scripts; env-driven CORS/docs **with** temporary fallback first.
3. **Tier 3** — Split `app.py` and routes behind smoke/regression tests; scheduler/worker split with a single owner.
4. **Tier 4** — Externalize secrets; remove client tracebacks; then remove unsafe fallbacks and fail-fast prod (**staging → production**).
5. **Tier 5** — Encryption key strategy with an explicit migration; CVV removal and tokenization with coordinated release and rollback plan.

---

## Cross-reference to audit phases

| Audit phase | Typical tiers involved |
|-------------|-------------------------|
| Phase 1 — Security fixes | Tier 4–5 (fallbacks, CVV, keys, secrets, CORS/docs, errors) |
| Phase 2 — Structure | Tier 3 (and Tier 1 duplicate cleanup if verified) |
| Phase 3 — Dependencies | Tier 2 |
| Phase 4 — Testing | Tier 1 |
| Phase 5 — PR gates | Tier 1–2 |
| Phase 6 — Deployment policy | Process; pairs with Tier 4 rollout discipline |

---

*Last aligned with `backend_audit.md` audit content; update this file when the audit or rollout plan changes.*
