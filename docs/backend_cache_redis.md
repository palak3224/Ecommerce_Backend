# Cache and Redis — current behavior (backend)

This document records **how caching and Redis work today** in this repository. It satisfies audit **§9** (*cache strategy inconsistent with codebase and planned infra*) at the **documentation** level; changing runtime behavior is a separate task.

**Related:** [backend_audit.md](./backend_audit.md) §9, [backend_audit_implementation.md](./backend_audit_implementation.md).

---

## Summary

| Layer | Behavior |
|--------|-----------|
| **Flask-Caching (`cache`)** | **Effectively off.** `CACHE_TYPE` is `null` in `config.py`, and **`create_app`** forces `CACHE_TYPE = 'null'` and removes `REDIS_URL` / `CACHE_REDIS_URL` before `cache.init_app(app)`. No Redis connection is attempted for the Flask-Caching extension in normal app startup. |
| **`@cached` decorator** (`common/cache.py`) | If `CACHE_TYPE == 'null'`, the decorator **runs the underlying function only** (no read/write through Flask-Caching). |
| **Direct Redis usage** | **`get_redis_client(app)`** is still used across the codebase. It is **independent** of Flask-Caching being null. It tries `app.config['REDIS_URL']` when present, otherwise **`redis://localhost:6379/0`**, then `ping()`. On any failure it returns **`None`** (and may log a warning if `app` is passed). |

So: **HTTP response caching via Flask-Caching is disabled by default**, but **feature code may still call Redis** when those code paths run.

---

## Where Redis is still referenced

Non-exhaustive list of **direct** `get_redis_client` (or wrapper) usage:

- `auth/controllers.py` — profile / session-style invalidation paths  
- `controllers/reels_controller.py` — reels-related caching  
- `services/recommendation_service.py` — recommendations  
- `controllers/follow_controller.py` — follow-related logic  
- `common/decorators.py` — decorators (e.g. rate-style checks)  
- `api/users/routes.py`  
- `routes/currency_routes.py` (imports; verify call sites)  
- **`services/translate_service.py`** — **translation result cache** (see risk below)

Many of these paths **degrade** when `get_redis_client` returns `None` (skips cache or no-ops). **Exception / risk:** `AmazonTranslateService` stores `self.redis = get_redis_client(current_app)` and calls **`self.redis.get` / `setex`** without guarding for `None`. If **`FEATURE_TRANSLATION`** is enabled and Redis is unavailable, those calls can **raise** (`AttributeError`). Treat **translation + Redis** as **must be validated** before enabling translation in an environment without Redis.

---

## Configuration knobs (today)

| Setting | Role |
|---------|------|
| `config.Config.CACHE_TYPE` | Declared as `'null'`; comment describes how Redis *would* be enabled for Flask-Caching. |
| `create_app` | Overwrites to `'null'` and pops Redis URL keys so Flask-Caching does not connect. |
| `FEATURE_TRANSLATION` | From env; gates registration of translate blueprint in `app.py`; does not by itself provision Redis. |
| `REDIS_URL` | Not set in default config for the main app path above; `get_redis_client` falls back to localhost if not on `app.config`. |

---

## Operations and ElastiCache

- **Provisioning ElastiCache today** does **not** speed up Flask-Caching for this app while `CACHE_TYPE` stays `null` and URLs are stripped in `create_app`.  
- ElastiCache becomes relevant when you **intentionally** re-enable Redis for either Flask-Caching or direct `get_redis_client`, with **documented** key prefixes, TTLs, and monitoring.

---

## Future work (not done in “Tier 1 — document” step)

- Either **remove or hard-disable** all Redis call paths until a product decision is made, **or** re-enable caching with a single supported configuration story.  
- Harden **`translate_service`** when `get_redis_client` returns `None` (skip cache, still call Translate API).  
- Align env vars (`REDIS_URL`, `CACHE_*`) with `create_app` so enabling Redis is deliberate and testable.

---

*If you change cache or Redis behavior, update this file in the same PR.*
