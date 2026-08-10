# Multi-currency (INR base, USD presentment) — working document

**Status:** Phase 0 complete. **Phase 4 backend complete** (server-authoritative checkout
quote), behind `FEATURE_QUOTE_ONLY_CHECKOUT`, default off. Phases 1–3 and 5–8 not started.
**Pending before deploy:** run `init_db.py` — Phase 4 adds three tables. See §11.
**Pending before the gate flips:** the frontend must send `quote_id`. See §8, Phase 4.
**Scope:** both repos — `Ecommerce_Backend/` and `Ecommerce/`.
**Audience:** whoever picks this up next, with no prior context.

Read this file top to bottom before touching any money code. The "Landmines" section
exists because several of these mistakes silently corrupt money data rather than failing
loudly.

**This document is the source of truth.** It supersedes any session plan file under
`.claude/plans/`, which is session-scoped and will not exist for you. For how to run,
build and test the two repos, see the root `CLAUDE.md`.

---

## 1. Why we are doing this

AOIN prices everything in INR. We are opening to the US, so:

- a visitor in India must see INR,
- a visitor anywhere else must see USD,
- a manual currency switcher must exist on the site,
- and none of the above may corrupt the order ledger, GST, merchant settlement,
  invoices, or reports.

The display layer is the easy part. Currency reaches much further than prices on a page:
it touches the order ledger, GST slab selection, platform-fee tiers, merchant payouts,
invoice PDFs (which are legal tax documents), and ~59 revenue aggregations.

---

## 2. Decisions already taken — do not re-litigate

These were decided deliberately. If you think one is wrong, raise it before changing it;
the rest of the design depends on them.

| Decision | Why |
|---|---|
| **INR is the base/book currency, permanently** | Merchants are Indian, prices are entered in INR, GST is computed on INR, Razorpay settles INR. |
| **USD is auto-derived** from a daily FX rate + markup + marketing rounding, with an **optional per-product override** | Requiring merchants to hand-enter a USD price for every product is an onboarding blocker before launch. The override exists so hero products can get a clean `$49.99`. |
| **Merchant + admin screens are currency-aware, with a base-currency (INR) toggle** | Chosen over "buyers only". Costs ~3× the frontend work and means every report needs currency grouping. |
| **Main marketplace first, then mirror to shop1–4** | The shop stack duplicates pricing/cart/order logic 1:1 with **zero shared code**. Doing both at once doubles the surface before the pattern is proven. |
| **Non-India destinations are zero-rated for GST** | Chosen deliberately. **Legally this requires a valid LUT or bond on file** — see §8. The code must refuse to zero-rate without `GST_EXPORT_LUT_NUMBER` set. |
| **Existing money columns stay INR; presentment goes in NEW columns** | See §3. This is the single most important architectural decision here. |
| **Currency travels as `?currency=USD`, not an `X-Currency` header** | Public product GETs send no custom headers today. A header turns every listing request into a CORS preflight round-trip and needs `allow_headers` changes in four places in `app.py`. A query param also keeps cache keys correct per currency. |
| **Checkout becomes quote-first** | Amount validation is otherwise *impossible*, not merely absent. See §5, defect #3. |

---

## 3. The load-bearing architectural choice

`orders.total_amount`, `order_items.line_item_total_inclusive_gst` and every existing
money column **stay INR forever**. Presentment (what the customer saw and paid) goes into
*new* columns: `presentment_currency`, `presentment_total_amount`, `fx_rate_to_base`,
`fx_rate_id`.

The rejected alternative was repurposing `total_amount` to hold presentment. Under that
scheme every one of the ~59 `func.sum()` aggregation sites must be found and changed, and
**any site missed silently sums mixed currencies** — a wrong revenue number that nobody
notices. Under the chosen scheme a missed site keeps summing INR, which is *correct*.

Fail-safe beats fail-dangerous when the failure mode is silent money corruption.

The cost: `services/invoice_service.py` must read presentment to show the customer what
they actually paid. One file, already covered by `tests/test_invoice.py`.

---

## 4. What the codebase looked like before we started

Facts gathered by exploration, so you don't have to re-derive them:

- **No currency layer existed.** `routes/currency_routes.py` is a FreeCurrencyAPI
  passthrough consumed only by `src/components/OrderSummary.tsx` for client-side FX math.
- `Order.currency` / `ShopOrder.currency` existed but defaulted to `"USD"` on INR amounts.
  `order_controller.py` wrote `config.DEFAULT_CURRENCY`, **a key that was never defined**,
  so the `"USD"` fallback is what actually landed on every order. The shop path wrote
  `'INR'`. **Every historical currency label is therefore meaningless.**
- **No server-side cart total exists at all.** Totals are computed in the browser.
- **Merchant balance is never stored.** `MerchantTransaction` rows are materialised on
  demand by an admin action.
- GST slab is selected by comparing the product price against an **INR threshold**
  (`GSTRule.price_condition_value`). Feed it USD and every product lands in the wrong band.
- Platform-fee tiers are hardcoded INR magnitudes: 500 / 2000 / 10000.
- Frontend: **235 `₹` literals across 66 files**, 18 separate local money formatters,
  **606 `fetch` call sites across 150 files**, no shared API client.

### Key coordinates

Line numbers are from the Phase 0 commit and will drift — treat them as "look here", not
as exact addresses.

| What | Where |
|---|---|
| Order total computation (the whole per-item loop) | `controllers/order_controller.py:62-162`, totals block `:138-148` |
| Which price is live (special vs selling) | `models/product.py:66` `get_current_listed_inclusive_price()` |
| GST back-calculation out of the inclusive price | `controllers/order_controller.py:100-106` |
| GST slab selection by INR threshold | `models/gst_rule.py:82-144` `find_applicable_rule()` |
| Shop order totals (the parallel implementation) | `controllers/shop/public/public_shop_order_controller.py:81-162` |
| Platform-fee tiers (hardcoded INR magnitudes) | `controllers/merchant_transaction_controller.py:11-18` |
| Merchant settlement row creation | `controllers/merchant_transaction_controller.py:46-90` |
| Invoice assembly (the only currency-aware code) | `services/invoice_service.py:91` `build_invoice_data()`, currency read at `:205` |
| Invoice money formatting | `services/invoice_pdf.py:20-24` `_fmt_money()` |
| Razorpay create-order | `routes/razorpay_routes.py` — `_resolve_amount_minor()` and the currency gate |
| Razorpay verify + (dead) write-back | `routes/razorpay_routes.py`, receipt correlation block |
| FX passthrough + leaked key | `routes/currency_routes.py:9`, key at `:70` |
| Client-side FX math (to be deleted) | `Ecommerce/src/components/OrderSummary.tsx:115-138` fetch, `:141-204` formatPrice |
| Checkout amount + currency assembly | `Ecommerce/src/pages/PaymentPage.tsx` — `createRazorpayOrder`, `handleOrder` |
| Cart price snapshots (client-cached) | `Ecommerce/src/context/CartContext.tsx:53-112` fetch, `:41-47` totals |
| Shop cart TTL cache | `Ecommerce/src/context/ShopCartContext.tsx:45-61` |
| Language switcher (pattern for the currency switcher) | `Ecommerce/src/components/common/Navbar.tsx:539-564` desktop, `:463-497` drawer |
| Provider nesting | `Ecommerce/src/App.tsx:313-320` |
| Auto-migration that fabricates defaults | `init_db.py:1204` `migrate_all_missing_columns`, `:1541` `_get_safe_default_for_type_improved` |

### Marketplace ↔ shop mirroring pairs

The shop stack shares **zero** pricing code with the marketplace. Any change on the left
almost certainly needs the same change on the right (Phase 8).

| Marketplace | Shop |
|---|---|
| `models/product.py` `serialize()` | `models/shop/shop_product.py` `serialize()` |
| `models/cart.py` `CartItem.serialize()` | `models/shop/shop_cart.py` `ShopCartItem.serialize()` |
| `models/order.py` `Order`/`OrderItem` | `models/shop/shop_order.py` `ShopOrder`/`ShopOrderItem` |
| `models/wishlist_item.py` | `models/shop/shop_wishlist.py` |
| `models/gst_rule.py` | `models/shop/shop_gst_rule.py` (additionally scoped by `shop_id`) |
| `controllers/order_controller.py` | `controllers/shop/public/public_shop_order_controller.py` |
| `controllers/cart_controller.py` | `controllers/shop/public/public_shop_cart.py` |
| `controllers/feature_product_controller.py` (heavy discount) | `controllers/shop/public/public_shop_product_controller.py` |

Divergences that trip up a naive copy: shop products have variants with `price_override`
and a `price_range`; `ShopShipmentItem` carries `unit_price` while the marketplace one does
not; marketplace `WishlistItem` snapshots `selling_price` while the shop one snapshots the
special-aware display price.

There are also two *intra*-marketplace duplications where the same endpoint has two
different price implementations: recently-viewed (controller vs an inline copy in
`routes/product_routes.py`) and cart items (`models/cart.py` vs an inline dict in
`routes/cart_routes.py`).

---

## 5. The live defects this work must fix

Found during exploration, except #5 which surfaced during Phase 4. #1, #2 and #5 were all
reachable in production.

1. **~85× overcharge.** `PaymentPage.tsx` sent a raw INR `finalTotal` while the currency
   came from the **phone dialling-code dropdown**. Selecting "+1" created a Razorpay order
   for the rupee figure denominated in USD. — **FIXED in Phase 0.**
2. **100× overcharge on cheap subscriptions.** `create-order` guessed the amount unit from
   magnitude ("an integer below 1000 is probably rupees"). `Subscription.tsx` sends paise,
   so a ₹9.99 plan sent `999` and was charged ₹999. — **FIXED in Phase 0.**
3. **The gateway write-back is dead code.** The Razorpay order is created *before* the
   internal `Order` exists, so `receipt` is a client-minted `ORDREF-<timestamp>` matching
   no row (`order_id` is a `String(50)`, so this fails silently rather than erroring).
   Even if it matched, the handler used `current_app.extensions['sqlalchemy'].db`, which
   raises `AttributeError` on Flask-SQLAlchemy 3.x, swallowed by `except Exception: pass`.
   — **FIXED.** Phase 0 fixed the `.db` bug and the silent swallow; Phase 4 fixed the
   correlation itself — the receipt is now the quote id, a row that exists before the
   gateway order does.
4. **The amount is entirely client-determined.** The browser computes `finalTotal` and the
   server trusts it. — **FIXED in Phase 4** on the quote path. `POST /api/checkout/quote`
   prices the basket server-side and `create-order` charges `quote.total_amount_minor`.
   The legacy client-amount path still exists until `FEATURE_QUOTE_ONLY_CHECKOUT` is
   turned on, so the hole is *closable*, not yet *closed*, in production.
5. **A client-supplied `razorpay_payment_id` marked an order PAID.** Found during Phase 4
   verification, not in the original sweep: `order_controller.py` flipped
   `payment_status` to SUCCESSFUL on the mere presence of that key in the request body,
   so posting any string produced a paid order with no money moved. — **FIXED in Phase 4.**
   Status now changes only when the server sets `payment_verified`, which happens after
   the gateway signature *and* the captured amount have both been checked.

---

## 6. What is DONE — Phase 0

Goal: stop the bleeding. No schema changes, no data migration, fully revertible with
`git revert`.

### Backend (`Ecommerce_Backend/`)

| File | Change |
|---|---|
| `config.py` | Added `DEFAULT_CURRENCY='INR'`, `HOME_COUNTRY_CODE='IN'`, `FEATURE_MULTI_CURRENCY` (default **false**). Added `FEATURE_MULTI_CURRENCY = False` to `TestingConfig`. |
| `routes/razorpay_routes.py` | Added `DEFAULT_CHARGE_CURRENCY`, `minor_unit_factor()`, `_resolve_amount_minor()`. `create-order` now rejects non-INR while the flag is off. Removed the magnitude heuristic. Fixed the `.db` bug and replaced `except Exception: pass` with logging. |
| `controllers/order_controller.py` | No longer honours a client-supplied currency — all amounts are computed from INR product prices, so the order is INR. |
| `models/order.py` | `currency` default `"USD"` → `"INR"`. |
| `models/shop/shop_order.py` | Same. |
| `tests/test_money_invariants.py` | **NEW.** INR defaults, config keys, serializer currency. |
| `tests/test_razorpay_order_creation.py` | **NEW.** Amount-unit resolution, incl. both overcharge regressions. |

**The amount contract now** — the caller must state its unit, we never guess:

```
amount_minor   integer minor units (paise/cents)     [preferred]
amount_major   decimal major units (rupees/dollars)  [preferred]
amount         LEGACY -> minor units   (Subscription.tsx sent paise)
amount_rupees  LEGACY -> major units   (PaymentPage.tsx sent rupees)
```

Legacy keys still resolve **correctly** so a stale cached SPA build cannot break. They log
a deprecation notice. Parsing uses `Decimal`, never `float` — `float("1234.565") * 100`
lands on `123456.4999…` and truncates to the wrong integer.

### Frontend (`Ecommerce/`)

| File | Change |
|---|---|
| `src/pages/PaymentPage.tsx` | Deleted `COUNTRY_TO_CURRENCY` + `getCurrencyForCountry`; added `CHECKOUT_CURRENCY = "INR"`. Sends `amount_major`. |
| `src/pages/business/Subscription.tsx` | Sends `amount_minor` instead of bare `amount`. |
| `src/components/home/Shop.tsx` | Fixed malformed JSX comment nesting (see §7). Dead commented-out markup only. |
| `package.json` | Added `"typecheck": "tsc --noEmit -p tsconfig.app.json"`. |

### Verification actually performed

- **`pytest` run against a real app context — 99 passed, 0 failed.** The two new files
  contribute 19 of those and all pass, including both overcharge regressions.
- All modified Python files pass `py_compile`.
- `npm run build` passes.
- `tsc` shows **no new errors** from these changes (the 512-error backlog in §7 is
  pre-existing: 305 `TS6133` + 126 `TS2322` + 81 assorted).

Reproduce:

```bash
cd Ecommerce_Backend
python -m venv venv && source venv/bin/activate   # venv/Scripts/activate on Windows
pip install -r requirments.txt                    # note the spelling
pytest tests/test_money_invariants.py tests/test_razorpay_order_creation.py -v
pytest                                            # then the whole suite
```

If you are ever on a machine where the deps cannot be installed, money-path *pure*
functions can still be exercised by injecting stub modules into `sys.modules`
(`razorpay`, `flask_jwt_extended`, `common.database`, `common.response`) and then importing
the real module. That is how `_resolve_amount_minor` was verified. It is a fallback for
pure logic only — it cannot test anything touching the DB or a request context, so it is
**not** a substitute for running `pytest`.

---

## 7. Known pre-existing problems (not caused by this work)

- **`tsc` reports 512 errors** — 305 unused-variable noise (`TS6133`), 126 real type
  mismatches (`TS2322`), rest assorted. These were hidden because a parse error in
  `Shop.tsx` (commit `9dfac04`, 2026-01-02) aborted the check early. Fixing that comment
  revealed the backlog. **`npm run typecheck` therefore cannot be a blocking CI gate yet.**
  Open decision: disable `noUnusedLocals` to clear ~318, or keep the script informational.
- **Two live API keys were hardcoded in tracked source, in a PUBLIC repository**
  (`github.com/palak3224/Ecommerce_Backend` is `visibility: PUBLIC`): a FreeCurrencyAPI
  key at `routes/currency_routes.py:70`, and an ExchangeRate-API key as the `os.getenv`
  *default* at `config.py:89`.

  Compounding it, `.env` spelled the variable **`EXCHANGE_RATE_API_KE`** — no trailing
  `Y` — so `os.getenv('EXCHANGE_RATE_API_KEY')` found nothing and the literal in the
  source was the key actually in use. Same shape as the `config.DEFAULT_CURRENCY` bug in
  §4: a name that was never defined, so the fallback quietly became production.

  **Both literals are now removed** from source; the route reads `FREECURRENCY_API_KEY`
  from env and returns 503 if it is unset, rather than falling back to anything. The
  route also no longer echoes the provider's error body back to callers.

  **Still required: rotate both keys at the providers.** They remain in git history and
  no code change reclaims them. `.env` itself was never committed (verified: zero commits
  touch it, no `.env` at any path in history), so the AWS / Twilio / Stripe / Cloudinary /
  mail secrets are not exposed.

  Open: `/api/exchange-rates` is still unauthenticated, so anyone can drain the quota on
  the new key. Add `@jwt_required()` or delete the route — Phase 2 replaces it regardless.
- ~~**The silent 1.0 FX fallback in the frontend.**~~ **FIXED.**
  `Ecommerce/src/components/OrderSummary.tsx` did `const rate = exchangeRates[currency] || 1;`,
  so a failed or incomplete `/api/exchange-rates` response printed the raw INR number under
  a `$` — 1299 shown as `$1299.00` rather than about `$15`. It now falls back to displaying
  the true INR amount and warns, instead of fabricating a rate. Keep this shape in mind for
  Phase 2: it is the same bug `test_fx_service.py::missing rate never returns 1.0` exists to
  prevent, and it had already shipped once.
- `controllers/superadmin/merchant_transaction_controller.py:63` references
  `item.final_price_for_item`, a *serializer key* (`models/order.py:178`) not a column →
  raises `AttributeError`.
- `controllers/merchant/report_controller.py:530` multiplies `line_item_total_inclusive_gst`
  by quantity, but that column is already quantity-inclusive (set at
  `order_controller.py:128`) → top-product revenue inflated. The other five `func.sum` sites
  in that file are correct; only `:530` has the extra factor.
- `models/gst_rule.py` declares `_tablename_` (single underscores), so the real table is
  `gst_rule`, not `gst_rules`. Any hand-written DDL must use the real name. Same typo on
  `_repr_`.
- `Ecommerce_Backend` contains committed stale duplicates (`auth 2/`, `routes 2/`,
  `.git 2/`, …). Never edit those.

---

## 8. What is REMAINING

### Phase 1 — Stamp the truth (additive schema + backfill)

New **nullable** columns on `orders` and `shop_orders`: `base_currency`,
`presentment_currency`, `presentment_total_amount`, `fx_rate_to_base`, `fx_rate_id`,
`presentment_snapshot_at`, `legacy_currency_label`.

`scripts/backfill_order_currency.py` — `--dry-run` / `--apply`, batches of 1000, resumable.
Predicate is **`WHERE base_currency IS NULL`**, never a date cutoff: that makes it
idempotent and makes it structurally impossible to re-stamp a genuine USD order later.
Every pre-cutover row is INR *regardless of its stored label*. Preserve the pre-image in
`legacy_currency_label` so the run is exactly reversible. Abort if `SUM(total_amount)`
changes.

Also switch `invoice_service.py` to read `base_currency` — this fixes mislabelled GST
invoices as a side effect.

### Phase 2 — FX infrastructure (dark)

`models/fx_rate.py` (**append-only**, unique on `(base, quote, as_of_date, source)` —
historical orders reference these rows by id), `models/currency_config.py`,
`services/fx_service.py` (pure `Decimal`; raises `StaleFxRateError`/`NoFxRateError` and
**never falls back to 1.0**), daily APScheduler job gated by `FEATURE_FX_SNAPSHOT`,
disabled in `TestingConfig`. Set `next_run_time=datetime.now()` or the interval trigger
waits a full period and leaves the table empty on cold boot.

### Phase 3 — Presentment read path (dark)

Per-product USD override column; serializers emit a `presentment` block when `?currency=`
is present **and** the flag is on; `GET /api/currency/context`. Amounts as **strings**,
never floats.

**The response contract — parallel scalar fields, not `{amount, currency}` objects.**

~150 frontend call sites treat `price` / `selling_price` / `total_amount` as bare numbers
and do arithmetic on them. Replacing `price: 1299` with `price: {amount: "15.99", …}`
breaks all of them in one deploy with no incremental path. Parallel scalars let the
frontend migrate file by file, and a stale cached build keeps working.

```jsonc
{
  "selling_price": 15.99,        // UNCHANGED KEY - value is in the response currency
  "selling_price_inr": 1299.00,  // NEW - always INR, always safe
  "currency": "USD",             // NEW - per object
  "price_source": "DERIVED",     // DERIVED | MERCHANT_OVERRIDE | CONVERTED
  "prices": {                    // NEW - the shape new consumers should target
    "list": {"amount": "15.99", "currency": "USD",
             "amount_base": "1299.00", "base_currency": "INR"},
    "special": null
  }
}
```

**The backward-compatibility guarantee is the query-param gate:** presentment differs from
INR *only* when the caller opts in with `?currency=`. A request without it returns
byte-identical JSON to today. That is what makes changing the meaning of the existing
scalar keys safe.

Plumbing: give `serialize()` an optional `currency=None` kwarg defaulting to a helper that
reads request state and falls back to INR outside a request context (jobs, PDF rendering).
**Do not thread the kwarg through every caller** — there are far too many.

### Phase 4 — Server-authoritative checkout quote (INR-only) — **BACKEND DONE**

Shipped, INR-only, behind `FEATURE_QUOTE_ONLY_CHECKOUT` (default **false**).

| Piece | Where |
|---|---|
| `checkout_quotes` + `checkout_quote_items` | `models/checkout_quote.py` |
| `payment_refunds` | `models/payment_refund.py` |
| All basket arithmetic, one implementation | `services/checkout_quote_service.py` |
| `POST /api/checkout/quote`, `GET /api/checkout/quote/<id>` | `routes/checkout_routes.py` |
| `create-order` prices from `quote_id` / `subscription_plan_id` | `routes/razorpay_routes.py` |
| `verify-payment` asserts capture vs quote, then materialises | `routes/razorpay_routes.py` |
| Quote → order as a **copy**, not a recompute | `OrderController.create_order_from_quote` |
| Client-asserted payment success removed | `order_controller.py`, `payment_verified` arg |

Design decisions worth knowing before changing any of it:

- **The client names intent, the server names money.** A quote request may say
  "product 7, quantity 2, promo code SUMMER10". Amounts in the request body are ignored
  and logged. `promo_code` is resolved against `promotions` server-side — the old
  client-supplied `item_discount_inclusive` is gone from this path.
- **Materialising an order copies the quote's stored line items.** There is no second
  pricing implementation to drift from the first, so "quote total == order total" holds
  by construction rather than by two code paths agreeing.
- **`total_amount_minor` is the integer the gateway is asked for and the integer the
  capture is compared against.** No rounding question can enter the assert.
- **Single use is a conditional UPDATE, not read-then-write.** `consume_quote` puts the
  precondition in the WHERE clause, so concurrent captures cannot both win on any
  backend or isolation level. A row lock would not have worked on SQLite in tests.
- **Receipt correlation is fixed**: the Razorpay receipt is the quote id.
- **Shipping is server-resolved** (`DEFAULT_SHIPPING_AMOUNT`, `FREE_SHIPPING_THRESHOLD`),
  defaulting to 0.00, which is what the marketplace charges today.

**Frontend migration — DONE.**

| Piece | Where |
|---|---|
| Typed quote client | `Ecommerce/src/utils/checkoutQuote.ts` |
| Quote before payment; `create-order` gets only `quote_id` | `PaymentPage.tsx` `handleOrder` |
| Order created by the server; page no longer POSTs `/api/orders` | `handleRazorpaySuccess` → `finalizeOrder` |
| Plan priced server-side | `Subscription.tsx` sends `subscription_plan_id` |

Notes for whoever touches this next:

- `createRazorpayOrder` takes **no amount, currency or receipt** any more. The receipt
  is the quote id.
- `finalizeOrder(orderId)` holds the post-payment work both paths need (merchant
  settlement rows, logistics, cart clear, confirmation). None of it may fail the
  order — the money has already moved.
- If a payment was made against a quote but `verify-payment` returns no order id, the
  page **refuses** to fall through to the legacy branch. A second order for one
  payment is worse than asking the customer to contact support.
- Before opening the gateway, the page compares the quote total to the displayed total
  and aborts on a mismatch rather than charging a different number than is on screen.

**Still to do before the gate can flip:**

1. Set `FEATURE_QUOTE_ONLY_CHECKOUT=true`, which makes a client-stated amount a 400.
   Do this only once the new frontend build is actually deployed — the flag rejects
   the legacy path that a stale cached SPA still uses.
2. Delete the legacy branch in `handleRazorpaySuccess` and `processOrderAfterPayment`
   once nothing reaches them.
3. The card-payment branch in `create_order` still simulates success
   (`payment_succeeded_simulation = True`). Untouched here, still a hole on that path.

**Promo semantics are load-bearing.** `services/checkout_quote_service.py`
`_resolve_line_discounts` must keep matching `POST /api/promo-code/apply` exactly —
that endpoint is what quotes the discount to the customer before checkout, so any
divergence either overcharges against the displayed total or gives money away. The
rules: sitewide fixed is one amount spread pro rata across the basket; targeted fixed
is `min(line_total, value)` per matching line; percentages apply per line; lookup is
case-insensitive. Per-unit storage rounds **down**, so a discount can never round up
past its own value.

### Phase 5 — Tax treatment and fees (dark)

`tax_treatment` (`DOMESTIC`/`EXPORT_ZERO_RATED`) + `destination_country_code` resolved from
`UserAddress.country_code` (a `String(3)` — may hold `IN` or `IND`, normalise it).
Zero-rating zeroes the *rate*; slab selection still runs on the INR price, which is what
keeps USD out of the threshold comparison. **`GST_EXPORT_LUT_NUMBER` must be set or the
code refuses to zero-rate.** Platform-fee tiers move to config, labelled INR, with an
assertion that `order.base_currency == 'INR'`.

### Phase 6 — Reports and the base-currency toggle

`GROUP BY base_currency`; read-time conversion with a visible "converted at rate X as of
DATE" banner; replace the ~15 hardcoded `"currency": "INR"` literals. Fix the two
pre-existing report bugs from §7 as their own commit so they survive a rollback.

### Phase 7 — Enable USD ← *only phase blocked on Razorpay activation*

Internal allowlist → 5% canary → 100%. **The kill switch must never rewrite stored rows.**
Orders captured in USD keep their frozen snapshot forever.

### Phase 8 — Shop stack mirror

Repeat 3–7 against `models/shop/`, `controllers/shop/public/`, `src/components/shop/shopN/`.
The shop checkout has **no Razorpay path at all** today, so it gets the quote-first design
from the start.

> Phase 1's backfill **must cover `shop_orders` in the same run**, even though shop feature
> work lands last. Splitting them leaves the two halves disagreeing about what money means.

### Frontend track — runs in parallel from Phase 1

`src/utils/currencyStore.ts` (module-level store, **not** React state — providers render
outer→inner but effects fire inner→outer, so a provider-effect install runs after
`CartProvider`'s first fetch) → `src/utils/money.ts` → `src/utils/apiClient.ts` (the
install-once fetch interceptor) → `CurrencyContext` → `useMoney` → `CurrencySwitcher` /
`BaseCurrencyToggle`.

Then migrate the 235 `₹` literals by surface: the 5 byte-identical `formatCurrency` copies
→ cart/checkout → storefront (flag flips here) → order history → merchant → superadmin →
creator → shop1–4. **While the store is pinned to INR, `formatMoney` output is byte-identical
to today's output**, so the intermediate state *is* the current state and the app is never
half-broken.

Switch behaviour: manual switch → persist + `window.location.reload()` (crude but provably
correct — 100+ pages hold prices in local state); async geo-confirm → granular invalidation;
**currency locks during checkout**.

**The fetch interceptor is the riskiest single step in the project.** Mandatory safeguards:
origin allowlist (must exclude the `127.0.0.1:7247` debug fetches in `main.tsx`/`App.tsx`/
`CartContext.tsx`, Cloudinary uploads, the Razorpay CDN); never overwrite an existing
`currency` param; preserve `Request` inputs; never touch `body`/`headers` (FormData uploads);
deny-list `/api/auth/*`; guard against HMR double-wrap.

---

### Test files to add, by phase

Follow `tests/test_invoice.py`'s self-contained fixture (`create_app("testing")` +
`db.create_all()` / `db.drop_all()`), not the bare `tests/conftest.py` app fixture — these
all need a DB.

| Phase | File | Key assertions |
|---|---|---|
| 1 | `test_currency_backfill.py` | USD-labelled legacy rows stamped INR; **no amount changes**; idempotent; **already-stamped rows untouched** (the re-conversion guard); `shop_orders` covered |
| 2 | `test_fx_service.py` | stale rate raises rather than falling back; **missing rate never returns 1.0**; markup + rounding to an exact `Decimal`; rows are append-only |
| 4 | `test_checkout_quote.py` | **WRITTEN — 25 tests, passing.** quote total == order total exactly; client amount ignored; quote expires; single-use; gateway refs committed (re-queried from a fresh session); rounding closure over fuzzed baskets; another user's quote not loadable; client-supplied payment id does not mark an order paid. *Gap: the capture-vs-quote mismatch rejection is implemented in `verify-payment` but not covered — it needs a mocked Razorpay client.* |
| 5 | `test_gst_multicurrency.py` | slab selection identical under USD; `find_applicable_rule` receives the INR price; export zero-rated; **refused without LUT**; domestic unchanged |
| 6 | `test_reports_currency.py` | revenue grouped by base currency; top-products not double-counted; superadmin summary does not raise; fee tier uses INR base |
| 4/7 | `test_refund_currency.py` | **WRITTEN — 5 tests, passing.** persisted; partials sum; failed attempts do not consume headroom; over-refund detectable; per-payment isolation. *Gap: the route-level guard is covered through the same summing function, not through a mocked gateway.* |

The single most valuable test in this list is `test_fx_service.py::missing rate never
returns 1.0`. A silent 1.0 fallback is how an $85 item becomes an ₹85 sale.

## 9. Landmines — how this silently corrupts money

1. Declaring a new FX/currency column **`NOT NULL`**. `init_db.py::migrate_all_missing_columns`
   auto-`ALTER`s from the model and `_get_safe_default_for_type_improved` fabricates
   `DEFAULT 0.00` for `Numeric` and `DEFAULT ''` for `String` — so every historical row gets
   FX rate zero, or a third bogus currency label. **Always `nullable=True`, no `default=`.**
2. `migrate_all_missing_columns` only **ADDs**, never **MODIFYs** — `orders.currency DEFAULT
   'USD'` survives in MySQL no matter what the model says. Needs a hand-written idempotent
   `ALTER` in `run_migrations.py`.
3. New **tables** only get created if imported — register them in `models/__init__.py` **and**
   the import block in `init_db.py`, or `db.create_all()` skips them.
4. Backfilling on a date predicate instead of `base_currency IS NULL` after go-live.
5. Re-adding any magnitude heuristic to the payment amount path.
6. Passing a USD amount into `calculate_platform_fee_percentage` — wrong tier, **persisted**,
   permanent under/over-payment of a merchant.
7. Cross-currency `func.sum()` producing a GMV number a business decision is made on.
8. Restarting gunicorn before running `init_db.py` — "Unknown column" on every order read.
9. Shipping the marketplace fix while `shop_orders` still defaults `'USD'`.
10. Re-converting historical orders at today's rate — refunds then won't match charges.

---

## 10. Invariants

| # | Invariant |
|---|---|
| I1 | Base columns are always INR |
| I2 | Stored presentment minor units + currency == what the gateway captured |
| I3 | Once paid, `presentment_*` and `fx_rate_*` are frozen |
| I4 | Every `fx_rate_id` resolves to a never-mutated row |
| I5 | Σ(lines) + shipping − discount == presentment total, **exactly** |
| I6 | GST selection derives only from INR values |
| I7 | `EXPORT_ZERO_RATED` ⟺ destination ≠ IN ⟺ tax 0 (and LUT on file) |
| I8 | `merchant_transactions` are always INR |
| I9 | No `float` in the money path; APIs emit strings |
| I10 | One capture ⟷ one quote ⟷ one order |
| I11 | Refund currency == capture currency; Σ refunds ≤ captured |
| I12 | No read path re-converts a historical order |

**Do not** write an invariant asserting `settled_INR == base_total_amount`. Razorpay settles
at *its* rate with *its* markup. Asserting equality would fire on every international order
and train everyone to ignore alerts — including I2, which is real.

---

## 11. Deploy runbook — schema first, code second, always

```
1. mysqldump orders / order_items / shop_orders / shop_order_items   (non-negotiable)
2. git pull                    # gunicorn NOT yet restarted
3. python init_db.py           # adds columns + creates new tables
4. python run_migrations.py    # column-default fix + presence assertions
5. python scripts/backfill_order_currency.py --dry-run
6. python scripts/backfill_order_currency.py --apply
7. systemctl restart gunicorn  # only now does code see the new columns
8. python scripts/verify_currency_invariants.py   # must print all-zero
```

Code rollback (reverse step 7) is safe — old code ignores extra columns. Schema rollback is
not required and should not be attempted.

**Phase 4 specifically** needs only steps 2, 3 and 7 — it adds three tables
(`checkout_quotes`, `checkout_quote_items`, `payment_refunds`) and no columns on existing
tables, so there is nothing to backfill and nothing to un-default. Landmine #3 applies:
the tables are registered in both `models/__init__.py` and `init_db.py`, and
`db.create_all()` skips anything that is not. With `FEATURE_QUOTE_ONLY_CHECKOUT` off,
deploying the code without running `init_db.py` still degrades safely — the quote endpoint
500s, checkout continues on the legacy path — but run it anyway.

---

## 12. Open decisions and external dependencies

**Waiting on a decision:**
- Typecheck stance — disable `noUnusedLocals` (clears ~318 of 512) or keep the script
  informational?
- Whether zero-rated export prices are GST-stripped. The INR list price is GST-inclusive;
  zero-rating an export means either the buyer pays the same inclusive price (merchant keeps
  the GST component) or the GST is stripped first (lower USD price). **The second is
  commercially and legally correct** and changes the price-book derivation input. Must be
  settled before Phase 3.

**External, with lead times — start now:**
- **Razorpay international activation.** Gates Phase 7 only. Day-one probe: try
  `client.order.create({amount: 1000, currency: 'USD'})` against the **test** key. If test
  mode allows it, Phases 4 and 7 rehearse fully on staging.
- **LUT / bond** for zero-rated exports. Gates Phase 5.
- **International shipping** — ShipRocket serviceability, HSN/customs, duties. A USD checkout
  that cannot ship is worse than no USD checkout.
- **Refund policy across FX movement.** A full refund returns the USD captured, which is not
  the INR captured at today's rate. Decide before the first international order, not after
  the first dispute.

---

## 13. Suggested next step

Phase 0 and the Phase 4 backend are done. Next, in order:

1. **Migrate the frontend checkout to `quote_id`**, then flip
   `FEATURE_QUOTE_ONLY_CHECKOUT`. Phase 4 reduces no real risk until the gate is on —
   the legacy client-amount path is still what production uses.
2. **Rotate the FreeCurrencyAPI key** (§7). Unrelated to any phase and still live.
3. **Phase 1** (stamp the truth) — additive, and it makes `invoice_service.py` stop
   mislabelling GST invoices as a side effect.
