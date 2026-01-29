# Creator / Influencer Module — PPT Image Prompts (V1)

This file is meant to help you generate **consistent visuals** for a research/functional presentation (dev + product + ops friendly).

You will use it like this:
1) Paste the **Pre‑Prompt** once into your image AI.
2) Then paste **one slide prompt at a time** (Slide 1, Slide 2, …) to generate each image.

---

## Pre‑Prompt (paste once before generating images)

You are generating a **consistent set of slide images** for a technical/product research presentation about the AOIN platform.

### Platform context (must remember)
- AOIN is an e‑commerce platform with **users**, **merchants**, **admins**, **super_admin**.
- We are proposing a new role: **Creator/Influencer**.
- Creators do **not** own products; they create reels to promote **merchant products** on AOIN.
- Merchants can create a **Deal/Campaign** to hire a creator for a specific product reel.
- Creator uploads a reel linked to a **campaign_id/campaign_code**, which links to a **product_id** and **merchant_id**.
- AOIN tracks sales attributed to creator reels using **last‑touch attribution** within a time window (example: 7 days).
- Commission rules (logic, not profit pitch): creator % (optionally capped by quantity) + fixed AOIN fee (example: 5%) on attributed sales.
- Settlement becomes eligible after **delivery + return window**; refunds reverse payouts.

### Visual style (keep consistent across all slides)
- Style: **clean vector**, modern SaaS diagrams, minimal, high contrast, professional.
- Background: white or very light gray.
- Palette (use consistently): Navy `#0B1F3B`, Teal `#12B3A8`, Orange `#F59E0B`, Gray `#6B7280`.
- Typography: clean sans-serif.
- Use simple icons: user, storefront, shield/admin, camera/creator, link, database, coin/wallet.
- Do **NOT** use photorealistic people. No clutter. No gradients unless subtle.
- Output: **16:9** landscape, suitable for PPT.
- Include **short labels** inside the diagram (2–4 words each). Keep text readable and minimal.
- IMPORTANT: avoid tiny text; prefer big labels and fewer items.

### Output requirement
Generate a single image per prompt that looks like a polished PPT slide visual.

---

## Slide 1 — Goal & Scope (V1)

**Image prompt:**
Create a 16:9 vector slide titled “Creator Module — Goal & Scope (V1)”.
Diagram: center headline box “Creator-driven Reels for AOIN Products”.
Below it, two columns:
Left column (In Scope V1): “Creator role”, “Category onboarding (5)”, “Deal/Campaign”, “Reel upload linked to campaign”, “Attribution (last-touch)”, “Settlement rules”.
Right column (Out of Scope for now): “Auto scraping external data”, “Advanced fraud engine”, “Affiliate integrations”, “Real-time external price sync”, “Complex ranking ML”.
Use icons: checklist for in-scope, crossed-circle for out-of-scope.

---

## Slide 2 — Roles & Permissions

**Image prompt:**
Create a 16:9 vector slide titled “Roles & Permissions”.
Show 5 role cards in a row with icons:
User, Merchant, Creator, Admin, Super Admin.
Under each card show 3–4 capability chips:
- User: “Browse”, “Buy”, “Watch reels”
- Merchant: “List products”, “Create campaigns”, “Approve reels”
- Creator: “Portfolio”, “Accept deals”, “Upload reels”
- Admin: “Moderate”, “Manage categories”
- Super Admin: “Platform control”, “Policy overrides”
Use consistent chip style, minimal text.

---

## Slide 3 — Core Entities (Data Objects)

**Image prompt:**
Create a 16:9 vector slide titled “Core Entities”.
Draw 5–6 connected boxes (like a data model map) with arrows:
CreatorProfile → Campaign/Deal → Reel → AttributionEvent → OrderItem → SettlementLedger.
Add key fields as 2–3 short bullet chips inside each box:
- CreatorProfile: “categories(5+)”, “portfolio”, “availability”
- Campaign: “product_id”, “creator_id”, “terms”, “status”
- Reel: “campaign_id”, “video”, “metrics”
- AttributionEvent: “user_id”, “reel_id”, “timestamp”
- OrderItem: “net_amount”, “attributed_campaign_id”
- SettlementLedger: “creator_commission”, “aoin_fee”, “merchant_net”
Use small database icon next to the chain to hint persistence.

---

## Slide 4 — Creator Onboarding Flow

**Image prompt:**
Create a 16:9 vector slide titled “Creator Onboarding (V1)”.
Show a left-to-right flow with 5 steps:
1) Sign up/login
2) Select 5 categories (mandatory)
3) Add portfolio (links/reels)
4) Set availability (available/busy)
5) Creator profile live
Use icons: login, tag/category, gallery/portfolio, toggle, check badge.
Add a side note bubble: “Categories enable merchant filtering”.

---

## Slide 5 — Merchant → Creator Matching

**Image prompt:**
Create a 16:9 vector slide titled “Merchant Finds Creators”.
Show merchant selecting a product card (with category tag).
Arrow to a filtered creator list UI mock:
Filters at top: “Category match”, “Language”, “Availability”.
List items show creator avatar icon + “portfolio” icon + “stats” icon.
Highlight that category filter is automatically applied from product category.
Keep it as a clean UI wireframe style (vector).

---

## Slide 6 — Deal/Campaign Lifecycle (State Machine)

**Image prompt:**
Create a 16:9 vector slide titled “Campaign Lifecycle”.
Draw a state machine with rounded nodes:
Draft → Sent → Accepted → Active → Submitted → Approved → Live → Completed.
Add two side paths:
- Rejected (from Sent)
- Cancelled/Expired (from Draft/Sent/Active)
Use color coding:
Blue for normal states, orange for review/approval states, gray for terminal states.
Add tiny role labels near transitions:
Merchant: creates/approves, Creator: accepts/submits, Admin: can override.

---

## Slide 7 — Creator Reel Upload Linked to Campaign

**Image prompt:**
Create a 16:9 vector slide titled “Creator Reel Upload (Linked Tracking)”.
Show creator upload screen wireframe:
- dropdown “Select Campaign” (shows active campaigns)
- optional input “Campaign Code”
- file upload “Video”
- “Submit”
Arrow from “Select Campaign” to a backend linkage diagram:
Reel → campaign_id → product_id → merchant_id.
Use a link/chain icon to emphasize binding.

---

## Slide 8 — Attribution Logic (Last‑Touch)

**Image prompt:**
Create a 16:9 vector slide titled “Attribution (Last‑Touch, Windowed)”.
Show a timeline with events:
1) User watches Reel
2) Clicks product from reel
3) Purchase happens later
Draw a rule box: “If purchase within 7 days of last reel→product click, attribute to that campaign”.
Add a second example beneath:
User sees Reel A then Reel B → purchase → “Reel B wins (last touch)”.
Use simple timeline graphics and minimal text.

---

## Slide 9 — Commission & Settlement (Logic Only)

**Image prompt:**
Create a 16:9 vector slide titled “Commission Split & Settlement”.
Show a formula diagram using 3 stacked boxes:
Net Sale Amount (after discount/refund) →
Split into:
1) Creator Commission (X%, optional cap qty)
2) AOIN Fee (5% on attributed sales)
3) Merchant Net (remaining)
Add an eligibility gate at top:
“Eligible after Delivery + Return Window”.
Add a refund arrow:
“Refund/Return → reverse ledger”.
Use coin/wallet icons, keep it neutral (no revenue hype).

---

## Slide 10 — Edge Cases & Controls

**Image prompt:**
Create a 16:9 vector slide titled “Edge Cases & Controls (V1)”.
Make a 2x3 grid of cards with icons + 1-line labels:
1) Wrong product linked → “Request changes”
2) Campaign expired → “Upload blocked”
3) Multiple reels touched → “Last-touch rule”
4) Refund after payout → “Ledger reversal”
5) Self-order risk → “Basic checks”
6) Moderation → “Admin disable reel”
Use shield/warning icons, clean style.

---

## Slide 11 — API & Integration Points (High Level)

**Image prompt:**
Create a 16:9 vector slide titled “APIs & Integration Points”.
Show three columns (Frontend / Backend / Database) with arrows:
Frontend boxes:
- “Creator profile”
- “Creator list & filter”
- “Create/accept campaign”
- “Upload reel (campaign-linked)”
- “Track click event”
Backend boxes:
- “Auth & roles”
- “Campaign service”
- “Reel service”
- “Attribution service”
- “Settlement service”
Database boxes:
- “creator_profiles”
- “campaigns”
- “reels”
- “attribution_events”
- “order_items (attributed)”
- “settlement_ledger”
Keep it conceptual (no code).

---

## Slide 12 — Implementation Phases (V1 → V2)

**Image prompt:**
Create a 16:9 vector slide titled “Implementation Phases”.
Draw a 3-lane roadmap:
Lane 1: Data model
Lane 2: Backend APIs
Lane 3: Frontend UI
Phase V1 (highlighted): roles + creator onboarding + campaign lifecycle + reel upload linking + attribution + basic settlement.
Phase V2 (lighter): ranking improvements + anti-fraud + automation + advanced analytics.
Use a timeline with 2 milestones: V1, V2.

---

## Optional Bonus Slide — Creator Portfolio Preview (UI Mock)

**Image prompt:**
Create a 16:9 vector slide titled “Creator Portfolio Preview”.
Design a clean profile card UI:
- creator name + categories badges
- portfolio grid (6 tiles)
- stats row (avg views, engagement, completed campaigns)
- button “Send Offer”
Keep it neutral, minimal, and consistent with the palette.

