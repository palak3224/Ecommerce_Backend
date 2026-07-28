# USA Marketplace — Payment Gateway & Logistics Choice

**Context:** AOIN is a **multi-vendor marketplace** (many sellers, one buyer checkout).
For the US market we must pick a **payment gateway** and a **logistics/shipping**
provider. The deciding factor is **not** the lowest per-transaction fee — it is
whether the provider supports **marketplace split payments** and **multi-seller
shipping**, because a marketplace pays out to *many* sellers and ships from *many*
locations per order.

---

## 1. Payment Gateway → **Stripe (Stripe Connect)**

### The choice
**Use Stripe — specifically its marketplace product, Stripe Connect.** PayPal as an
optional secondary checkout button later.

### Why Stripe (for a marketplace)
- **Split payments are native (Stripe Connect).** One buyer payment is automatically
  split to each seller's connected account, with AOIN's commission deducted — no
  manual payouts, no holding funds. This is the single most important marketplace
  requirement, and Connect is the US industry standard for it.
- **Handles seller onboarding & KYC/compliance.** Connect verifies each seller's
  identity and bank details (required to legally pay them). We don't have to build
  this from scratch.
- **Best developer API of any gateway** — fastest to integrate into our custom
  backend; supports subscriptions, Apple Pay, Google Pay.
- **We already have Stripe test keys** in the project, so groundwork exists.
- **Transparent pricing, no contract:** 2.9% + $0.30 per transaction, no monthly/
  setup fee (Connect adds a small per-payout fee).

### Why not the others
| Gateway | Why not (for a US marketplace) |
|---------|-------------------------------|
| **PayPal** | Good as a *secondary* checkout button for conversion, but weaker for custom split-payout flows. Use it *alongside* Stripe, not instead. |
| **Square** | Best when you also sell **in person** (POS). We're online-only → its POS strength is wasted; less specialized for marketplace/subscription billing. |
| **Authorize.Net** | Adds a **$25/mo** fee and a dated dashboard; better suited to businesses that already have their own merchant account. Not worth it early. |
| **Adyen** | Enterprise-only — heavy setup (€500–€5,000+) and monthly platform fees, and it charges per authorization attempt (even failed ones). Only makes sense at very large scale ($250K+/month). |

### Verdict
> **Stripe Connect** — it's the only mainstream US gateway purpose-built to split one
> payment across many sellers with automatic commission + seller KYC. Add **PayPal**
> as a secondary checkout option later to lift conversion.

---

## 2. Logistics / Shipping → **EasyPost**

### The choice
**Use EasyPost as the multi-carrier shipping API**, with **USPS + UPS** enabled as the
two carriers (add FedEx / a regional carrier later based on volume & geography).

### Why EasyPost (for a marketplace, specifically)
- **Multi-seller / multi-pickup fits its model.** A marketplace order can contain items
  from several sellers, each shipping from their **own address** → one order becomes
  **multiple shipments**. EasyPost is API-native and built for exactly this kind of
  custom, multi-origin routing.
- **Generous free volume: 3,000 labels/month free**, then $0.08/label. With many
  sellers each printing labels, that free ceiling matters far more than a slightly
  lower per-label price.
- **Largest carrier network (100+ carriers)** and a 99.99% uptime SLA — so any seller,
  in any region, can find a carrier.
- **One integration, many carriers.** USPS (cheapest for light parcels), UPS (heavier/
  B2B), FedEx (express), and regional carriers are all just toggles inside EasyPost —
  no separate integrations per carrier.

### EasyPost vs Shippo (the close call)
Both are excellent multi-carrier APIs. For a **multi-vendor** app we lean **EasyPost**:

| | **EasyPost** ✅ | Shippo |
|--|----------------|--------|
| Free tier | **3,000 labels/mo** | 30 labels/mo |
| Carriers | 100+ | 40+ |
| Built for | Custom apps / complex routing | Also great, slightly SMB-oriented |
| Per-label above free | $0.08 | $0.05 (cheaper) |

Shippo is **cheaper per label**, so if cost-per-label were the only axis, Shippo wins.
But for a marketplace with **many sellers generating many labels**, EasyPost's **free
3,000/month** and **wider carrier coverage** outweigh the small per-label difference.
*(If volume stays low and cost-per-label is the priority, Shippo is a perfectly valid
alternative.)*

### Carriers to enable inside EasyPost
- **USPS** — default/cheapest for light parcels (<5 lb); covers every US address incl.
  PO boxes & rural. Your primary carrier leg.
- **UPS** — secondary, for heavier / higher-value / B2B shipments.
- **FedEx / Regional (OnTrac, LSO, Veho)** — add later based on order weight/geography.

### Verdict
> **EasyPost** — its free 3,000 labels/month, 100+ carriers, and API-native multi-origin
> design make it the best fit for a marketplace where many sellers ship from many
> locations. Enable **USPS + UPS** first; expand carriers as volume grows.

---

## Summary

| Layer | **Choose** | One-line reason |
|-------|-----------|-----------------|
| **Payments** | **Stripe (Connect)** | Native split payments to many sellers + seller KYC + best API; PayPal as secondary later. |
| **Logistics** | **EasyPost** (USPS + UPS) | Multi-seller/multi-pickup friendly, 3,000 free labels/mo, 100+ carriers, one API. |

**The rule behind both choices:** for a marketplace, pick the provider that natively
handles **many sellers** — split payouts on the payment side, multi-origin shipments on
the logistics side — not just the one with the lowest headline fee.

---

*Pricing figures are per public July 2026 vendor pages and can change — confirm current
rates before signing up. Planning guidance only; not financial or legal advice.*
