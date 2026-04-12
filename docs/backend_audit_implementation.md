# Backend audit — implementation tracker

This document ties each finding in **[backend_audit.md](./backend_audit.md)** to **what we did** or **what is still planned**. Update it as work lands.

**Related:** [backend_audit_priorities.md](./backend_audit_priorities.md) (risk tiers and sequencing).

---

## How to maintain this document (required after each step)

Whenever you finish an audit or Tier-priority **implementation step**, do **all** of the following in the **same change** (or immediately after):

1. **Append** a new block under **[Step-by-step implementation log](#step-by-step-implementation-log)** using the template:
   - **Step** — number + name (e.g. “Tier 1 — step 4: …”).
   - **Maps to** — audit § number(s) and/or [backend_audit_priorities.md](./backend_audit_priorities.md) row.
   - **Issue** — what was wrong or missing (one short paragraph or bullets).
   - **Solution** — exactly what we shipped (files, commands, env vars, workflows).
   - **Date** — optional but recommended (`YYYY-MM-DD`).
2. **Update** the **[Progress summary](#progress-summary-living)** table and the **Status / Implementation** for the matching numbered § section above.

This keeps a chronological record of **issue → solution** for every step, not only the high-level § summaries.

---

## Step-by-step implementation log

### Step 1 — Tier 1: pytest and smoke tests

| | |
|--|--|
| **Maps to** | Audit **§7** (no test suite); [backend_audit_priorities.md](./backend_audit_priorities.md) Tier 1 — “Add pytest and `tests/`”. |
| **Issue** | No `tests/` directory, no `pytest.ini`, no automated checks that the app factory boots or that a minimal HTTP endpoint works. Changes could regress startup without detection. |
| **Solution** | Added **`tests/conftest.py`** with `app` / `client` fixtures calling **`create_app("testing")`**. Added **`tests/test_smoke.py`**: asserts testing config (SQLite URI, `TESTING=True`) and **`GET /health`** returns `{"status":"ok"}`. Added **`TestingConfig`** in **`config.py`** (in-memory SQLite, `NOTIFICATION_CLEANUP_ENABLED=False`, fixed test secrets). Wired **`get_config(config_name)`** and **`create_app(config_name=None)`** in **`app.py`** so tests use `testing` and production/dev still follow `FLASK_ENV` when `create_app()` is called with no args. Added **`pytest.ini`** (`testpaths`, `pythonpath`, `filterwarnings` for Flask-Caching noise). |
| **Date** | 2026-04 (baseline) |

---

### Step 2 — Tier 1: compileall in CI

| | |
|--|--|
| **Maps to** | Audit **sanity check** / **Phase 5** (syntax verification); priorities Tier 1 — “`python -m compileall` in CI”; also supports **§7** “visible CI”. |
| **Issue** | No automated syntax pass on push/PR; `compileall` was manual only. |
| **Solution** | Added monorepo workflow **[`.github/workflows/ecommerce-backend-compileall.yml`](../../.github/workflows/ecommerce-backend-compileall.yml)**: on changes under `Ecommerce_Backend/`, runs Python 3.12 and `python -m compileall -q` with `-x` excluding `venv`, `.venv`, `__pycache__`. Documented equivalent local command in priorities doc. |
| **Date** | 2026-04 (baseline) |

---

### Step 3 — Tier 1: structured logging (partial §11)

| | |
|--|--|
| **Maps to** | Audit **§11** (ad hoc `print`, operational noise); priorities Tier 1 — “Structured logging”. |
| **Issue** | `services/s3_service.py` and other paths used **`print`** for debugging; no single log format or JSON option for aggregators; duplicate stderr usage (e.g. creator OTP) alongside `logger.error`. |
| **Solution** | Added **`common/logging_config.py`** with **`configure_app_logging(app)`** (`LOG_LEVEL`, `LOG_FORMAT=json` for one JSON line per event). Invoked from **`create_app`** after config load. Replaced **`print`** with **`logging` / `current_app.logger`** in **`s3_service.upload_product_media`**, **`controllers/product_controller.py`**, **`routes/product_routes.py`**, **`models/shop/shop_cart.py`**, and removed redundant **`print`/`traceback.print_exc`** in **`auth/controllers.py`** creator verify OTP handler after `exc_info=True` logging. **Not done in this step:** chatbot tracebacks, global error JSON to clients, redaction, `merchant_routes` STAGE prints, CLI `print` in `app.py` `__main__` / `start_servers.py`. |
| **Date** | 2026-04 (baseline) |

---

### Step 4 — Tier 1: document cache / Redis reality (partial §9)

| | |
|--|--|
| **Maps to** | Audit **§9** (cache vs Redis inconsistency); [backend_audit_priorities.md](./backend_audit_priorities.md) Tier 1 — “Document cache/Redis reality”. |
| **Issue** | Teams could assume “no Redis” because Flask-Caching is null, while **`get_redis_client`** and translation still relate to Redis; ElastiCache value was unclear; no single place described behavior. |
| **Solution** | Added **[`docs/backend_cache_redis.md`](./backend_cache_redis.md)** (summary table, Flask-Caching vs direct Redis, call-site list, `FEATURE_TRANSLATION` risk, ElastiCache note, future work). Updated **`common/cache.py`** module docstring and **`get_redis_client` docstring**; **`config.py`** and **`app.py`** cache block comments with pointer to that doc; **`services/translate_service.py`** module doc points to doc for Redis absence. **Not done:** guard `translate_service` when Redis is `None`, remove Redis paths, or re-enable Flask-Caching Redis intentionally. |
| **Date** | 2026-04-03 |

---

## Status legend

| Status | Meaning |
|--------|--------|
| **Done** | Delivered in repo; behavior or process matches the intent of the finding (may still have follow-ups). |
| **Partial** | Some of the required direction is in place; more work remains under the same finding. |
| **Not started** | No implementation yet; follow audit “Required direction.” |
| **N/A** | Process/infra only; tracked separately if needed. |

---

## Progress summary (living)

**Last updated:** Tier 1 — step 4 cache/Redis documentation (partial §9).

| # | Area | Status | Short note |
|---|------|--------|------------|
| — | **Automated syntax check (audit sanity / Phase 5)** | **Done** | GitHub Actions runs `python -m compileall` on `Ecommerce_Backend` (see workflow path below). |
| 7 | **Test suite foundation (part of §7)** | **Partial** | `pytest`, `tests/`, smoke tests (`create_app("testing")`, `GET /health`), `TestingConfig`, `pytest.ini`. Not yet: pytest in CI, auth/cart/order/payment/admin coverage, full PR gate. |
| 9 | **Cache / Redis documentation (part of §9)** | **Partial** | **[`docs/backend_cache_redis.md`](./backend_cache_redis.md)** + code pointers. Not yet: translate guard, disable paths or intentional Redis re-enable. |
| 11 | **Operational logging (part of §11)** | **Partial** | Central `configure_app_logging`; `LOG_LEVEL`, `LOG_FORMAT=json`; removed request-path `print` in `s3_service`, `product_controller`, `product_routes`, `shop_cart`, duplicate stderr in creator OTP. Not yet: chatbot tracebacks, app-wide error handler sanitization, secret redaction. |

**Tier 1 completed so far:** (1) pytest + smoke tests, (2) compileall CI, (3) structured logging (partial §11), (4) cache/Redis doc + comments (partial §9).

---

## 1. Critical: Configuration falls back to unsafe defaults

**Problem (audit)**  
`SECRET_KEY`, `JWT_SECRET_KEY`, `DATABASE_URI`, exchange-rate key, Razorpay test creds, and defaulting to `DevelopmentConfig` when `FLASK_ENV` is missing allow production to boot with insecure settings.

**Target solution (audit)**  
Remove secret/credential fallbacks; fail fast when required env vars are missing; default to production-safe behavior.

**Status:** Not started  

**Implementation**  
—  

---

## 2. Critical: CVV is stored in the database

**Problem (audit)**  
`payment_card` model and controller persist and decrypt CVV; retention after authorization is not acceptable even if encrypted.

**Target solution (audit)**  
Remove CVV persistence; move to tokenized payment flows; reassess card-storage design for production.

**Status:** Not started  

**Implementation**  
—  

---

## 3. High: Card encryption key handling is unsafe

**Problem (audit)**  
`CARD_ENCRYPTION_KEY` from env only; `init_db.py` can generate a new Fernet key if missing — risks unreadable data and inconsistent environments.

**Target solution (audit)**  
Stable key from Secrets Manager / Parameter Store; no new production key generation in app init; rotation via controlled migration only.

**Status:** Not started  

**Implementation**  
—  

---

## 4. High: Application entrypoint and route layer too large

**Problem (audit)**  
Very large `app.py`, `superadmin_routes.py`, `merchant_routes.py`, `reels_controller.py` — high regression risk, weak testability.

**Target solution (audit)**  
Split app factory vs routes vs middleware vs errors; domain-sized route modules; business logic in services/use-cases.

**Status:** Not started  

**Implementation**  
—  

---

## 5. High: Dependency management is weak

**Problem (audit)**  
Unpinned `requirments.txt`, duplicate entries, mixed API / chatbot / AI / reporting packages; two MySQL drivers, two WSGI servers, etc.

**Target solution (audit)**  
Pinned sets; split manifests (main API, chatbot/AI, dev/test); one MySQL driver; one production WSGI strategy.

**Status:** Not started  

**Implementation**  
—  

---

## 6. High: Dependency ownership needs cleanup

**Problem (audit)**  
Direct imports should be explicit (e.g. `cryptography`, `pydantic`, `celery`, `langchain-core`); several packages need workload-specific review before staying on main API runtime.

**Target solution (audit)**  
Declare direct deps; verify optional/heavy packages by workload; do not remove transitive needs blindly.

**Status:** Not started  

**Implementation**  
—  

---

## 7. High: No visible backend test suite or PR quality gate

**Problem (audit)**  
No `tests/`, no `pytest.ini` / `tox.ini`, no visible backend CI — changes ship without behavioral checks.

**Target solution (audit)**  
Unit tests; create-app smoke tests; auth, cart, order, payment, admin regression tests; require checks on every PR.

**Status:** **Partial**  

**Implementation (done so far)**  
- **`tests/`** — `conftest.py` (fixtures using `create_app("testing")`), `test_smoke.py` (testing config assertions, `GET /health` → `{"status":"ok"}`).  
- **`config.py`** — `TestingConfig` (in-memory SQLite, no notification scheduler noise, fixed test secrets).  
- **`app.py`** — `create_app(config_name=None)` uses `get_config(config_name)`; `create_app("testing")` used by tests. Production/dev entrypoints unchanged when calling `create_app()` with no args (still driven by `FLASK_ENV`).  
- **`pytest.ini`** — `testpaths`, `pythonpath`, and filters for known Flask-Caching noise during tests.  

**Still to do (same finding)**  
- Run **pytest** in CI (e.g. extend GitHub Actions: install `requirments.txt`, `pytest tests/`).  
- Add regression coverage: auth, cart, orders, payment safety, admin authorization.  
- Broader **PR gate**: lint, security scanners, etc. (audit Phase 5).  

---

## 8. High: API exposure broader than it should be

**Problem (audit)**  
Static `ALLOWED_ORIGINS` in code; `/docs` exposed; chatbot duplicates CORS and runs a public Flask app.

**Target solution (audit)**  
Origins from environment; disable or protect docs in production; consistent security headers and CORS across services.

**Status:** Not started  

**Implementation**  
—  

---

## 9. Medium: Cache strategy inconsistent with codebase and infra

**Problem (audit)**  
Cache forced to `null` but Redis helpers and code paths remain; translation may assume Redis when enabled.

**Target solution (audit)**  
Document reality; either remove/guard Redis paths or re-enable caching with ownership and TTLs; fix translation when Redis is absent.

**Status:** **Partial**  

**Implementation (done so far)**  
- **[`docs/backend_cache_redis.md`](./backend_cache_redis.md)** — authoritative description: Flask-Caching null vs `get_redis_client`, file references, translation risk, ElastiCache note, future work.  
- **Code pointers:** `common/cache.py` (module + `get_redis_client` docs), `config.py` / `app.py` cache comments, `services/translate_service.py` module doc.  

**Still to do (same finding)**  
Guard or skip Redis in **`translate_service`** when client is `None`; optionally remove Redis-only paths until product decision; or re-enable caching with env + tests.  

---

## 10. Medium: Not safely scale- or zero-downtime-ready

**Problem (audit)**  
`BackgroundScheduler` in web process; health without clear readiness/drain/shutdown; mixed startup in `app.py`; no rollout verification pipeline.

**Target solution (audit)**  
Out-of-process scheduling; stateless web tier; readiness/graceful shutdown; migration discipline; post-deploy smoke checks.

**Status:** Not started  

**Implementation**  
—  

---

## 11. Medium: Error and operational logging need tightening

**Problem (audit)**  
Stack traces in logs/handlers; chatbot returns tracebacks to clients; `s3_service` prints internals.

**Target solution (audit)**  
Sanitized client errors; full traces in restricted logs only; structured logging; redact secrets.

**Status:** **Partial**  

**Implementation (done so far)**  
- **`common/logging_config.py`** — `configure_app_logging(app)` after config load in `create_app`. Env: `LOG_LEVEL` (default `INFO`), `LOG_FORMAT=text|json` (JSON = one object per line on stderr).  
- **`services/s3_service.py`** — `upload_product_media` no longer uses `print`; uses `current_app.logger` with `info` / `debug` and %-formatting for stable field-like messages.  
- **`controllers/product_controller.py`**, **`routes/product_routes.py`**, **`models/shop/shop_cart.py`** — module `logging.getLogger(__name__)`; errors use `logger.exception` / `logger.warning`; noisy diagnostics at `debug`.  
- **`auth/controllers.py`** — creator verify OTP path: removed redundant `print` / `traceback.print_exc` after `logger.error(..., exc_info=True)`.  

**Still to do (same finding)**  
Sanitized API error payloads; chatbot client responses; `app.py` global handler behavior; redact tokens in logs; remaining `print` in CLI scripts (`app.py` `__main__`, `start_servers.py`, `merchant_routes` debug stages, migrations).  

---

## 12. Medium: Repository hygiene (duplicate trees)

**Problem (audit)**  
Duplicate directories (`auth 2`, `common 2`, `controllers 2`, `routes 2`, etc.) and `requirments 2.txt`.

**Target solution (audit)**  
Single source of truth; fix imports after removal.

**Status:** Not started  

**Implementation**  
—  

---

## Automation outside numbered notes (sanity check / CI)

**Audit reference**  
Sanity check: `python -m compileall -q .` — syntax only, not runtime correctness.

**Status:** **Done** (for CI enforcement of compileall)

**Implementation**  
- **Monorepo:** [`.github/workflows/ecommerce-backend-compileall.yml`](../../.github/workflows/ecommerce-backend-compileall.yml)  
- Triggers on changes under `Ecommerce_Backend/`; runs `compileall` with Python 3.12, excluding `venv` / `.venv` / `__pycache__` in the path regex.  
- **Local (same as CI):**  
  `cd Ecommerce_Backend && python -m compileall -q -x '/(\.venv|venv|__pycache__)/' .`  

---

## Backend plan phases (from audit) — quick map

Use this as a checklist; detail lives in **backend_audit.md** § Backend Plan.

| Phase | Theme | Tracker |
|-------|--------|---------|
| 1 | Security (config, CVV, keys, secrets, CORS/docs, errors) | §1–3, §8, §11 |
| 2 | Structure & maintainability | §4, §12, chatbot isolation |
| 3 | Dependencies | §5–6 |
| 4 | Testing | §7 (expand), §10 (smoke for deploy) |
| 5 | PR gates & CI/CD | §7, compileall ✓, add pytest/lint/audit tools |
| 6 | Deployment policy | Process + infra doc |

---

*Reminder: after each implementation step, append **[Step-by-step implementation log](#step-by-step-implementation-log)** (Issue + Solution) and refresh **Progress summary** + the relevant § section.*
