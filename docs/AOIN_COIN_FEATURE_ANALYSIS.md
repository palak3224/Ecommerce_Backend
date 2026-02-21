# AOIN Coin Feature – Analysis Report

This document is an **analysis report** for introducing **AOIN Coin**—a digital in-app currency—within the AOIN Store e-commerce application. It covers scope, use cases, technical considerations, integration points, risks, and recommendations.

---

## 1. Executive summary

**AOIN Coin** is proposed as an in-app digital currency that users and optionally merchants can **earn** (e.g. via engagement, referrals, rewards) and **spend** (e.g. discounts on orders, tips, or exclusive perks) within the AOIN ecosystem. This report outlines what the feature could look like, how it fits with existing modules (orders, payments, reels, merchants), what to build from a technical standpoint, and what to watch from a legal and product perspective.

**Recommendation:** Treat AOIN Coin as a phased initiative: start with a clear definition (earn vs spend rules, redemption value), then implement a minimal ledger and balance layer, integrate with one or two high-value flows (e.g. order discount or reel/referral rewards), and only then expand to more use cases after validation and compliance review.

---

## 2. Definition and scope

### 2.1 What is AOIN Coin?

- **Nature:** A non-withdrawable, in-app digital currency (sometimes called “virtual currency” or “loyalty points with monetary label”). It is **not** legal tender and is **not** convertible to cash or other external currencies unless explicitly allowed by policy and law.
- **Unit:** Coins are typically integer or fixed-decimal (e.g. 1 Coin = 1 unit; or 100 Coins = ₹1 for redemption).
- **Owners:** Primarily **end-users (customers)**. Optionally **merchants** could hold or earn coins in a separate bucket (e.g. for promotions or rewards), but the first phase is often user-only.

### 2.2 Scope for this analysis

- **In scope:** Earning mechanisms, spending/redemption mechanisms, balance storage, transaction ledger, APIs, and integration with existing AOIN modules (users, orders, payments, reels).
- **Out of scope (for this report):** Final legal/compliance sign-off, exact redemption rates, UI/UX flows, and marketing copy. Those should be owned by legal, product, and design.

---

## 3. Use cases (earn and spend)

### 3.1 Earning AOIN Coins (users)

| Use case | Description | Considerations |
|----------|-------------|----------------|
| **Order reward** | User earns X coins per order or per ₹ spent. | Define rate (e.g. 1% of order value), min/max per order, exclusions (refunds, cancelled). |
| **Reels engagement** | Coins for watching, liking, sharing, or creating reels. | Risk of abuse (fake engagement); caps, rate limits, and fraud checks. |
| **Referral** | Coins for referring new users (and optionally when referee places first order). | Need referral tracking and attribution; define eligibility and caps. |
| **Reviews / UGC** | Coins for writing product reviews, uploading photos. | Quality and moderation; limit per product/user. |
| **Sign-up / onboarding** | One-time or milestone bonuses. | One-time per user; KYC/verification if needed later. |
| **Promotions** | Campaign-based grants (e.g. “Double coins this week”). | Time-bound; clear terms. |

### 3.2 Spending AOIN Coins (users)

| Use case | Description | Considerations |
|----------|-------------|----------------|
| **Order discount** | Redeem coins at checkout (e.g. 100 coins = ₹10 off). | Fix conversion (coins → INR), max discount per order, min order value; integrate with order and payment flow. |
| **Unlock content / perks** | Spend coins to access certain reels, products, or features. | Define which content and pricing. |
| **Tip / support creators** | Send coins to merchants or creators (e.g. on reels). | If allowed, need recipient balance and possibly merchant payout policy. |

### 3.3 Merchant-side (optional)

- **Earning:** Coins for performance (e.g. sales targets, quality metrics) or promotions run by platform.
- **Spending:** Merchants spend coins on visibility (e.g. boost reels) or promotions.  
Merchant coin flows can be phase 2 once user coins are live and stable.

---

## 4. Technical analysis

### 4.1 Core entities (suggested)

- **Wallet / Balance:** Per user (and optionally per merchant). Stores current coin balance. Enforce single source of truth and consistency with ledger.
- **Ledger / Transaction log:** Immutable log of every credit and debit (who, amount, type, reference_id, reason_code, created_at). Enables balance recomputation and audit.
- **Transaction types:** Enum or codes for earn (e.g. ORDER_REWARD, REEL_VIEW, REFERRAL, PROMO) and spend (e.g. ORDER_REDEEM, TIP, BOOST).

### 4.2 Balance and consistency

- **Updates:** Every change (credit/debit) = one ledger row and one balance update (or balance derived from ledger). Prefer **single-writer** (e.g. one service or lock per user) to avoid race conditions.
- **Idempotency:** For critical flows (e.g. order reward, order redeem), use idempotency keys so duplicate requests do not double-credit or double-debit.
- **Negative balance:** Define policy (e.g. not allowed; reject spend if insufficient balance).

### 4.3 Integration points in current system

| Existing module | Integration with AOIN Coin |
|-----------------|----------------------------|
| **Users / Auth** | Wallet and ledger are per user_id; JWT used for all coin APIs. |
| **Orders** | On order success: credit “order reward” coins; at checkout: allow “apply coins” and create a spend transaction; ensure order total and payment (e.g. Razorpay) account for coin discount. |
| **Payments (Razorpay)** | Order amount after coin discount = amount charged to customer; backend must pass discounted amount to Razorpay and record coin debit. |
| **Reels** | On view/like/share (or creator upload): optional coin credit; respect caps and rate limits. |
| **Merchants** | If merchant coins are introduced: link wallet/ledger to merchant_id; define earn/spend rules. |
| **Referrals** | Referral module (if any) triggers coin credit when referee signs up or places first order. |

### 4.4 APIs (suggested)

- **GET /api/coin/balance** – Current user’s coin balance (and optionally expiry breakdown if you support expiring coins).
- **GET /api/coin/transactions** – Paginated history (credits/debits) for the user.
- **POST /api/coin/apply-at-checkout** – Validate and return applicable discount for a given order (idempotent; does not debit until order is confirmed).
- **Internal / server-side:** Credit or debit triggered by order completion, referral, reel event, or admin grant. Not exposed directly to client without server-side validation.

### 4.5 Expiry and limits (optional)

- **Expiry:** If coins expire (e.g. after 12 months), store expiry_period or expiry_date per grant; balance = sum of non-expired. Complicates logic; can be phase 2.
- **Caps:** Max balance, max earn per day/week per type, max redeem per order. Stored as config or in business logic.

---

## 5. Compliance and risks

### 5.1 Legal and regulatory

- **Virtual currency / e-money:** In many jurisdictions, non-withdrawable in-app currency used only for in-app benefits is treated as “closed-loop” and may be subject to lighter regulation than cash-out or convertible currency. Still, legal review is recommended.
- **Tax:** Income to user (earned coins) or discount (spent coins) may have tax implications for platform or user depending on jurisdiction. Consult tax advisor.
- **Terms of use:** Clearly state that AOIN Coins are not cash, not redeemable for cash unless stated, and subject to platform terms; reserve right to modify earn/spend rules and expiry.

### 5.2 Fraud and abuse

- **Fake engagement:** Reel or referral abuse to farm coins. Mitigations: rate limits, caps, anomaly detection, and manual review.
- **Double redemption:** Use idempotency and strict order–coin flow (debit only once per successful order).
- **Chargebacks:** If user pays via Razorpay and later chargebacks, define policy: whether coin reward for that order is reversed.

### 5.3 Operational

- **Support:** Disputes over missing coins or failed redemption. Need audit trail (ledger) and clear rules.
- **Reversals:** Refunds/cancellations: define if and how coin reward is reversed or redeem is rolled back.

---

## 6. Phased implementation (recommended)

| Phase | Focus | Deliverables |
|-------|--------|--------------|
| **0 – Definition** | Product and legal alignment | Fixed conversion (coin ↔ INR), earn/spend rules, caps, expiry (if any), terms. |
| **1 – Foundation** | Ledger and balance | DB schema (wallets, ledger), APIs: balance and transaction history; internal credit/debit; no expiry in v1. |
| **2 – First earn** | One earn path | e.g. Order reward: on order success, credit coins; show in UI. |
| **3 – First spend** | One spend path | Order discount at checkout: apply coins, reduce order amount, debit coins on payment success; integrate with Razorpay. |
| **4 – More use cases** | Reels, referrals, etc. | Additional earn (reels, referrals) and optional spend (tips, boosts) with caps and monitoring. |
| **5 – Optional** | Merchant coins, expiry | If needed: merchant wallets, expiry logic, advanced anti-abuse. |

---

## 7. Open questions for product and legal

1. **Conversion:** How many AOIN Coins = ₹1 (or vice versa) for redemption? Same rate for earn (e.g. ₹100 order = X coins)?  
2. **Caps:** Max balance per user? Max earn per day/per type? Max redeem per order or per month?  
3. **Expiry:** Do coins expire? If yes, after how long and with what notice?  
4. **Cash-out:** Will users ever be able to withdraw coins to bank/cash? If no, state clearly in terms.  
5. **Merchant coins:** Required for MVP or later?  
6. **Refund/cancel:** On order refund, are earned coins clawed back and redeemed coins returned?  
7. **Jurisdiction:** Which country/countries is the product offered in? Any specific e-money or gaming regulations to consider?

---

## 8. Summary

- **AOIN Coin** is an in-app digital currency for the AOIN Store: users (and optionally merchants) earn and spend coins within the app.
- **Earn:** Order rewards, reels engagement, referrals, reviews, sign-up, promos.
- **Spend:** Order discount, unlock content, tip creators (and optionally merchant-side spend).
- **Technical:** Wallet + ledger, single-writer balance updates, idempotency for order-related flows, clear integration with orders and Razorpay.
- **Risks:** Legal/regulatory, tax, fraud/abuse, refunds; address via terms, caps, and audit trail.
- **Recommendation:** Define rules and conversion first; then implement ledger and balance; then one earn (e.g. order reward) and one spend (order discount); then expand and add merchant/expiry if needed.

This report can be used to align engineering, product, and legal before implementation and to drive a phased AOIN Coin roadmap.
