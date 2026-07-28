"""Render the US marketplace provider-choice doc to a styled PDF."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

NAVY = colors.HexColor("#1F3A5F")
ORANGE = colors.HexColor("#F2631F")
GREY = colors.HexColor("#5B6670")
LIGHT = colors.HexColor("#F5F7FA")
GREEN = colors.HexColor("#2E7D32")
DARK = colors.HexColor("#1F2A37")

styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=NAVY, fontSize=22, spaceAfter=4, leading=26)
SUB = ParagraphStyle("SUB", parent=styles["Normal"], textColor=GREY, fontSize=10.5, spaceAfter=6, leading=14)
H2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=NAVY, fontSize=15, spaceBefore=14, spaceAfter=6, leading=18)
H3 = ParagraphStyle("H3", parent=styles["Heading3"], textColor=ORANGE, fontSize=11.5, spaceBefore=8, spaceAfter=3, leading=14)
BODY = ParagraphStyle("BODY", parent=styles["Normal"], fontSize=10, leading=14.5, textColor=DARK, spaceAfter=5)
BULLET = ParagraphStyle("BULLET", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=3)
CELL = ParagraphStyle("CELL", parent=styles["Normal"], fontSize=9, leading=12, textColor=DARK)
CELLH = ParagraphStyle("CELLH", parent=CELL, textColor=colors.white, fontName="Helvetica-Bold")
VERDICT = ParagraphStyle("VERDICT", parent=BODY, fontSize=10.5, leading=15, textColor=NAVY,
                         leftIndent=8, borderPadding=6)
NOTE = ParagraphStyle("NOTE", parent=styles["Normal"], fontSize=8, leading=11, textColor=GREY, italic=True)

el = []


def b(text):
    return Paragraph("• " + text, BULLET)


def table(rows, col_widths, header=True, header_bg=NAVY):
    data = []
    for r in rows:
        data.append([Paragraph(c, CELLH if (header and i == 0) else CELL) if not hasattr(c, "wrap") else c
                     for c in ([Paragraph(x, CELLH) for x in r] if (header and rows.index(r) == 0)
                               else [Paragraph(x, CELL) for x in r])])
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D6DCE2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
    ]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), header_bg))
    t.setStyle(TableStyle(style))
    return t


# ---- Title ----
el.append(Paragraph("USA Marketplace — Payment &amp; Logistics Choice", H1))
el.append(Paragraph("AOIN multi-vendor marketplace &nbsp;|&nbsp; Provider decision &amp; rationale &nbsp;|&nbsp; July 2026", SUB))
el.append(HRFlowable(width="100%", thickness=1.2, color=NAVY, spaceAfter=8))

el.append(Paragraph(
    "<b>Context.</b> AOIN is a <b>multi-vendor marketplace</b> (many sellers, one buyer checkout). "
    "The deciding factor is <b>not</b> the lowest per-transaction fee — it is whether the provider supports "
    "<b>marketplace split payments</b> and <b>multi-seller shipping</b>, because a marketplace pays out to many "
    "sellers and ships from many locations per order.", BODY))

# ---- Payments ----
el.append(Paragraph("1. Payment Gateway → Stripe (Stripe Connect)", H2))
el.append(Paragraph("The choice", H3))
el.append(Paragraph("Use <b>Stripe — specifically its marketplace product, Stripe Connect.</b> "
                    "PayPal as an optional secondary checkout button later.", BODY))
el.append(Paragraph("Why Stripe (for a marketplace)", H3))
el.append(b("<b>Split payments are native (Stripe Connect).</b> One buyer payment is automatically split to each "
            "seller's connected account, with AOIN's commission deducted — no manual payouts, no holding funds. "
            "This is the single most important marketplace requirement."))
el.append(b("<b>Handles seller onboarding &amp; KYC/compliance.</b> Connect verifies each seller's identity and bank "
            "details (legally required to pay them). We don't build this from scratch."))
el.append(b("<b>Best developer API of any gateway</b> — fastest to integrate; supports subscriptions, Apple Pay, Google Pay."))
el.append(b("<b>We already have Stripe test keys</b> in the project, so groundwork exists."))
el.append(b("<b>Transparent pricing, no contract:</b> 2.9% + $0.30 per transaction; no monthly/setup fee "
            "(Connect adds a small per-payout fee)."))

el.append(Paragraph("Why not the others", H3))
el.append(table([
    ["Gateway", "Why not (for a US marketplace)"],
    ["PayPal", "Good as a <i>secondary</i> checkout button for conversion, but weaker for custom split-payout flows. Use alongside Stripe, not instead."],
    ["Square", "Best when you also sell <b>in person</b> (POS). We're online-only, so its POS strength is wasted; less specialized for marketplace/subscription billing."],
    ["Authorize.Net", "Adds a <b>$25/mo</b> fee and a dated dashboard; better for businesses that already have their own merchant account. Not worth it early."],
    ["Adyen", "Enterprise-only — heavy setup (€500–€5,000+), monthly platform fees, charges per authorization attempt (even failed). Only at very large scale ($250K+/mo)."],
], [32 * mm, 142 * mm]))
el.append(Spacer(1, 6))
vt = Table([[Paragraph("<b>Verdict:</b> Stripe Connect — the only mainstream US gateway purpose-built to split one "
                       "payment across many sellers with automatic commission + seller KYC. Add PayPal as a secondary "
                       "checkout option later to lift conversion.", VERDICT)]], colWidths=[174 * mm])
vt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("LINEBEFORE", (0, 0), (0, -1), 3, ORANGE),
                        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
el.append(vt)

# ---- Logistics ----
el.append(Paragraph("2. Logistics / Shipping → EasyPost", H2))
el.append(Paragraph("The choice", H3))
el.append(Paragraph("Use <b>EasyPost as the multi-carrier shipping API</b>, with <b>USPS + UPS</b> enabled as the two "
                    "carriers (add FedEx / a regional carrier later based on volume &amp; geography).", BODY))
el.append(Paragraph("Why EasyPost (for a marketplace, specifically)", H3))
el.append(b("<b>Multi-seller / multi-pickup fits its model.</b> A marketplace order can hold items from several "
            "sellers, each shipping from their <b>own address</b> → one order becomes <b>multiple shipments.</b> "
            "EasyPost is API-native and built for this multi-origin routing."))
el.append(b("<b>Generous free volume: 3,000 labels/month free</b>, then $0.08/label. With many sellers printing "
            "labels, this free ceiling matters more than a slightly lower per-label price."))
el.append(b("<b>Largest carrier network (100+ carriers)</b> and a 99.99% uptime SLA — any seller, any region, "
            "finds a carrier."))
el.append(b("<b>One integration, many carriers.</b> USPS (cheapest light parcels), UPS (heavier/B2B), FedEx "
            "(express), regional carriers — all just toggles inside EasyPost."))

el.append(Paragraph("EasyPost vs Shippo (the close call)", H3))
el.append(table([
    ["", "EasyPost  (chosen)", "Shippo"],
    ["Free tier", "3,000 labels/mo", "30 labels/mo"],
    ["Carriers", "100+", "40+"],
    ["Built for", "Custom apps / complex routing", "Great too, slightly SMB-oriented"],
    ["Per-label above free", "$0.08", "$0.05 (cheaper)"],
], [40 * mm, 70 * mm, 64 * mm], header_bg=GREEN))
el.append(Spacer(1, 4))
el.append(Paragraph("Shippo is <b>cheaper per label</b>, so if cost-per-label were the only axis, Shippo wins. But for a "
                    "marketplace with <b>many sellers generating many labels</b>, EasyPost's <b>free 3,000/month</b> and "
                    "<b>wider carrier coverage</b> outweigh the small per-label difference. (If volume stays low and "
                    "cost-per-label is the priority, Shippo is a valid alternative.)", BODY))

el.append(Paragraph("Carriers to enable inside EasyPost", H3))
el.append(b("<b>USPS</b> — default/cheapest for light parcels (&lt;5 lb); covers every US address incl. PO boxes &amp; rural."))
el.append(b("<b>UPS</b> — secondary, for heavier / higher-value / B2B shipments."))
el.append(b("<b>FedEx / Regional (OnTrac, LSO, Veho)</b> — add later based on order weight/geography."))
el.append(Spacer(1, 6))
vt2 = Table([[Paragraph("<b>Verdict:</b> EasyPost — its free 3,000 labels/month, 100+ carriers, and API-native "
                        "multi-origin design make it the best fit for a marketplace where many sellers ship from many "
                        "locations. Enable USPS + UPS first; expand carriers as volume grows.", VERDICT)]], colWidths=[174 * mm])
vt2.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("LINEBEFORE", (0, 0), (0, -1), 3, GREEN),
                         ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                         ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
el.append(vt2)

# ---- Summary ----
el.append(Paragraph("Summary", H2))
el.append(table([
    ["Layer", "Choose", "One-line reason"],
    ["Payments", "<b>Stripe (Connect)</b>", "Native split payments to many sellers + seller KYC + best API; PayPal secondary later."],
    ["Logistics", "<b>EasyPost</b> (USPS + UPS)", "Multi-seller/multi-pickup friendly, 3,000 free labels/mo, 100+ carriers, one API."],
], [26 * mm, 44 * mm, 104 * mm]))
el.append(Spacer(1, 6))
el.append(Paragraph("<b>The rule behind both choices:</b> for a marketplace, pick the provider that natively handles "
                    "<b>many sellers</b> — split payouts on payments, multi-origin shipments on logistics — not just the "
                    "one with the lowest headline fee.", BODY))

el.append(Spacer(1, 10))
el.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#D6DCE2"), spaceAfter=6))
el.append(Paragraph("Pricing figures are per public July 2026 vendor pages and can change — confirm current rates before "
                    "signing up. Planning guidance only; not financial or legal advice.", NOTE))


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(18 * mm, 12 * mm, "AOIN · USA Marketplace Provider Choice")
    canvas.drawRightString(192 * mm, 12 * mm, "Page %d" % doc.page)
    canvas.restoreState()


doc = SimpleDocTemplate(
    "/Users/nikhilpatel/Projects/aoin/Ecommerce_Backend/docs/US_MARKETPLACE_PROVIDER_CHOICE.pdf",
    pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
    title="USA Marketplace — Payment & Logistics Choice",
)
doc.build(el, onFirstPage=_footer, onLaterPages=_footer)
print("SAVED")
