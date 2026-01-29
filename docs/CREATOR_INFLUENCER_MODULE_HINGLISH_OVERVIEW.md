# Creator / Influencer Module (Hinglish Overview) — AOIN

### Ye feature kya hai?
AOIN me hum **ek naya role** add kar rahe hain: **Creator / Influencer**.  
Creator ka kaam hai **AOIN ke merchant products** ke liye reels banana aur AOIN app par upload karna.  
Merchant creators ko **hire** karega (deal/campaign ke through) aur jo sales creator ke reel se aayengi, uske basis par **commission/payout** hoga.

Iska simple aim:
- **Merchant**: product marketing creators se karwa sake
- **Creator**: reels banake commission earn kare
- **AOIN**: attribution track kare + platform fee + payouts manage kare

---

### Roles (high level)
- **User/Customer**: reels dekhe, product open kare, purchase kare
- **Merchant**: product list karta hai, creator ko hire karta hai, reels approve karta hai
- **Creator/Influencer (NEW)**: portfolio maintain karta hai, deals accept karta hai, reels upload karta hai
- **Admin/Super Admin**: moderation/override, disputes handle, creator/merchant control (optional)

---

## 1) Creator side (Influencer dashboard + flow)

### A) Creator signup / login ka flow
**Signup (Creator)**
- Basic: name, email/phone, password (ya OAuth later)
- Verification: email/phone verification (recommended)
- **Creator onboarding (mandatory)**:
  - “Aap kis-kis category me reels banate ho?” → **minimum 5 categories mandatory**
  - Language preferences (optional)
  - Portfolio links / sample reels (optional but recommended)
  - Availability toggle: **Available / Busy**

**Login**
- Same auth system, but role = `creator`
- Login ke baad redirect: **Creator Dashboard**

> Note: Creator merchant nahi hai, isliye uske paas product listing/stock features nahi honge.

### B) Creator dashboard me kya-kya hoga? (V1 suggested)
Creator Dashboard tabs (simple):
- **Home/Overview**
  - Active deals count, pending approvals, earnings summary, upcoming deadlines
- **My Categories**
  - Selected 5+ categories (edit allowed with limits)
- **Portfolio**
  - Portfolio items (links, uploaded showcase reels, social handles)
- **Deals/Campaigns**
  - Offers received (Accept/Reject)
  - Active campaigns (submit reel, deadline, terms)
  - Completed campaigns (history)
- **Upload Reel**
  - “Select Campaign” dropdown (sirf active campaigns assigned to creator)
  - Upload video + description
  - Submit for merchant approval
- **Earnings & Payouts**
  - Pending earnings, eligible earnings, paid history
  - Bank/UPI setup (jab payout implement ho)
- **Settings**
  - Profile edit, availability, notification prefs

---

## 2) Merchant side (dashboard options + flow)

### A) Merchant dashboard me kya add hoga?
Merchant Dashboard me ek naya section:
- **Creator Marketing / Creator Campaigns**
  - Find Creators (filter)
  - Create Campaign (offer)
  - Manage Campaigns (approve reels, track attributed sales)
  - Payout/Commission summary (creator wise)

### B) Merchant ka “creator hire” flow
1) Merchant product select kare (AOIN product)  
2) System automatically product ki category se creators filter karke dikhaye:
   - category match creators list
   - portfolio preview
   - availability
3) Merchant creator select kare aur **Deal/Campaign offer** create kare:
   - product_id
   - creator_id
   - terms (creator commission % + optional cap qty + campaign window)
   - deliverables: “1 reel” (V1)
4) Creator accept kare → campaign **Active**

---

## 3) AOIN side (platform process / tracking / governance)

### A) Campaign/Deal lifecycle (V1)
Statuses (simple):
- Draft → Sent → Accepted → Active → Submitted → Approved → Live → Completed  
Side states:
- Rejected (creator rejects)
- Cancelled/Expired (merchant/admin action or timeout)

### B) AOIN ka “tracking” kaise hoga? (attribution)
Problem: AOIN ko kaise pata chale ki sale kis creator reel se aayi?

**Solution (V1)**: reel ko campaign se bind kar do:
- Reel upload ke waqt creator **campaign select** kare
- Reel record me `campaign_id` store hoga
- Campaign me already `product_id` + `merchant_id` + `creator_id` present hoga

So chain becomes:
**Reel → Campaign → Product → Merchant + Creator**

### C) “Trade code” (human-friendly)
Campaign ka ek:
- internal `campaign_id` (system)
- short `campaign_code` (human-friendly)
Creator upload me dropdown primary, campaign_code optional fallback.

---

## 4) Reel upload process (Creator)

### V1: Creator reel upload ka rule
- Creator sirf **assigned campaigns** ke under hi reel upload kar sakta hai
- Reel upload screen:
  - Select Campaign
  - Upload video file
  - Add description
  - Submit

**Merchant Approval (recommended in V1)**
- Reel public feed me tabhi jaaye jab merchant approve kare
- Reason: wrong product / quality / compliance issues handle ho sakte hain

---

## 5) Commission calculation (logic)

### A) Commission terms (Deal me define)
V1 me 2 basic options:
1) **Percent + cap**  
   Example: “20% commission up to 200 quantity”
2) **Percent unlimited**  
   Example: “10% on all attributed sales”

Fixed rule:
- **AOIN fee**: 5% on attributed sales (sirf campaign-attributed sales par)

### B) Attribution rule (V1 simple)
**Last-touch attribution**:
- User reel dekhta hai → product open karta hai → purchase karta hai  
If purchase **within X days** (example: 7 days) of the last reel→product click, then campaign attribute ho jaati hai.

Multiple reels touched:
- last-touch wins (simple + industry standard)

### C) Commission base amount (recommended)
Commission “net” pe nikle:
- `net = item_price - item_discount - refunds`
Shipping/tax ko exclude rakhna (clear + disputes kam).

---

## 6) Payment / payout process (how money flows)

### A) Overall flow (conceptual)
1) Customer pays for order (existing payment flow)
2) Order delivered + return window over → sale becomes “eligible”
3) Eligible attributed sales ke basis par ledger entries generate:
   - Creator earning
   - AOIN fee
   - Merchant net (informational)
4) Creator payout initiated (weekly/monthly or threshold-based)

### B) Eligibility rule (recommended)
Payout eligible tab:
- Order status = delivered
- Return/refund window pass (e.g., 7/14 days)

### C) Refund/return handling
If refund/return happens:
- Creator payout reverse/adjust (ledger reversal)
- AOIN fee reversal (if already counted)

> Note: exact trigger points current order/payment implementation pe depend karenge (delivery status, refund workflows).

---

## 7) Important edge cases (V1 decisions)

### Creator selection / quality
- Category selection mandatory (5)
- Portfolio mandatory optional (but recommended)
- Availability toggle

### Wrong reel/product
- Merchant can reject / request changes
- Reel doesn’t go live until approved (recommended)

### Fraud / self-orders (future)
V1 minimal:
- block attribution if buyer == creator/merchant (same user id)
V2:
- device/session signals, abnormal patterns, manual review

### Multiple products in one reel
V1: avoid; keep **one reel → one product**.

---

## 8) What we will build (deliverables list)

### Backend (V1)
- New role: `creator`
- Creator profile (categories, portfolio, availability)
- Campaign/Deal module (create, accept, status, terms, code)
- Reel upload linking to campaign (creator upload path)
- Attribution events (reel→product click logging)
- Settlement ledger (eligible earnings calculation)
- Admin moderation hooks (optional)

### Frontend (V1)
- Creator signup/login + onboarding (5 categories)
- Creator dashboard (deals, upload, earnings)
- Merchant dashboard: “Creator Campaigns” section
- Product page / reel feed integration for attribution click event

---

## 9) V1 scope vs later (simple)

### V1 (focus)
- Creator onboarding + category based discovery
- Campaign offers + creator accepts
- Campaign-linked reel upload + merchant approval
- Last-touch attribution + basic settlement logic

### Later (V2)
- Advanced ranking/recommendations for creators
- Strong anti-fraud + dispute module
- Automation: auto campaign suggestions, batch payouts, advanced analytics

