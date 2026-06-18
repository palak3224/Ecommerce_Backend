# services/invoice_pdf.py
"""Render invoice data (from invoice_service.build_invoice_data) to PDF bytes via reportlab.

Defensive: every field access falls back to a safe default so a partially-populated
invoice still renders rather than throwing.
"""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

BRAND_COLOR = colors.HexColor("#F2631F")


def _fmt_money(currency, value):
    try:
        return f"{currency} {float(value):,.2f}"
    except Exception:
        return f"{currency} 0.00"


def _addr_lines(addr):
    if not addr:
        return ["N/A"]
    lines = []
    if addr.get("contact_name"):
        lines.append(f"<b>{addr['contact_name']}</b>")
    if addr.get("address_line"):
        lines.append(addr["address_line"])
    city_line = ", ".join(p for p in [addr.get("city"), addr.get("state_province"), addr.get("postal_code")] if p)
    if city_line:
        lines.append(city_line)
    if addr.get("country_code"):
        lines.append(addr["country_code"])
    if addr.get("contact_phone"):
        lines.append(f"Phone: {addr['contact_phone']}")
    return lines or ["N/A"]


def render_invoice_pdf(data):
    """Return PDF bytes for the given invoice data dict."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"Invoice {data.get('invoice_number', '')}",
    )
    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    small = ParagraphStyle("small", parent=normal, fontSize=8, leading=11)
    h_title = ParagraphStyle("title", parent=styles["Heading1"], textColor=BRAND_COLOR, fontSize=20)
    h_sec = ParagraphStyle("sec", parent=styles["Heading4"], spaceAfter=2)
    right = ParagraphStyle("right", parent=normal, alignment=2)

    currency = data.get("currency", "INR")
    elems = []

    # Header: title + invoice meta
    order_date = data.get("order_date")
    date_str = order_date.strftime("%d %b %Y, %H:%M") if hasattr(order_date, "strftime") else str(order_date or "")
    header = Table(
        [[
            Paragraph("AOIN", h_title),
            Paragraph(
                f"<b>TAX INVOICE</b><br/>Invoice No: {data.get('invoice_number', '')}<br/>"
                f"Order ID: {data.get('order_id', '')}<br/>Date: {date_str}",
                right,
            ),
        ]],
        colWidths=[90 * mm, 84 * mm],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elems.append(header)
    elems.append(Spacer(1, 8))

    # Seller + Buyer blocks
    seller = data.get("seller", {})
    seller_lines = [f"<b>{seller.get('business_name', 'Seller')}</b>"]
    if seller.get("address"):
        seller_lines.append(seller["address"])
    sc_line = ", ".join(p for p in [seller.get("city"), seller.get("state_province")] if p)
    if sc_line:
        seller_lines.append(sc_line)
    if seller.get("gstin"):
        seller_lines.append(f"GSTIN: {seller['gstin']}")
    if seller.get("pan_number"):
        seller_lines.append(f"PAN: {seller['pan_number']}")
    if data.get("multi_seller"):
        seller_lines.append("<i>(Order contains items from multiple sellers)</i>")

    seller_para = Paragraph("<br/>".join(seller_lines), small)
    bill_para = Paragraph("<br/>".join(_addr_lines(data.get("buyer_billing"))), small)
    ship_para = Paragraph("<br/>".join(_addr_lines(data.get("buyer_shipping"))), small)

    party = Table(
        [
            [Paragraph("Sold By", h_sec), Paragraph("Billing Address", h_sec), Paragraph("Shipping Address", h_sec)],
            [seller_para, bill_para, ship_para],
        ],
        colWidths=[58 * mm, 58 * mm, 58 * mm],
    )
    party.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.lightgrey),
    ]))
    elems.append(party)
    elems.append(Spacer(1, 10))

    # Line items table
    head = ["#", "Item", "Qty", "GST%", f"Taxable ({currency})", f"Tax ({currency})", f"Total ({currency})"]
    rows = [head]
    for li in data.get("line_items", []):
        name = li.get("name", "Item")
        if li.get("sku"):
            name += f"<br/><font size=6 color='#888888'>SKU: {li['sku']}</font>"
        if li.get("merchant_name"):
            name += f"<br/><font size=6 color='#888888'>Sold by: {li['merchant_name']}</font>"
        rows.append([
            str(li.get("sl", "")),
            Paragraph(name, small),
            str(li.get("quantity", 0)),
            f"{float(li.get('gst_rate', 0)):.0f}%",
            f"{float(li.get('taxable_value', 0)):,.2f}",
            f"{float(li.get('tax_amount', 0)):,.2f}",
            f"{float(li.get('line_total', 0)):,.2f}",
        ])
    items_tbl = Table(rows, colWidths=[8 * mm, 66 * mm, 12 * mm, 14 * mm, 26 * mm, 22 * mm, 26 * mm], repeatRows=1)
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_COLOR),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elems.append(items_tbl)
    elems.append(Spacer(1, 10))

    # Tax summary (CGST/SGST or IGST or single GST)
    tax_mode = data.get("tax_mode", "GST")
    if tax_mode == "CGST_SGST":
        tax_head = ["GST%", f"Taxable ({currency})", f"CGST ({currency})", f"SGST ({currency})"]
        tax_rows = [tax_head]
        for r in data.get("tax_summary", []):
            tax_rows.append([
                f"{float(r.get('rate', 0)):.0f}%",
                f"{float(r.get('taxable', 0)):,.2f}",
                f"{float(r.get('cgst') or 0):,.2f}",
                f"{float(r.get('sgst') or 0):,.2f}",
            ])
        tax_widths = [20 * mm, 34 * mm, 34 * mm, 34 * mm]
    elif tax_mode == "IGST":
        tax_head = ["GST%", f"Taxable ({currency})", f"IGST ({currency})"]
        tax_rows = [tax_head]
        for r in data.get("tax_summary", []):
            tax_rows.append([
                f"{float(r.get('rate', 0)):.0f}%",
                f"{float(r.get('taxable', 0)):,.2f}",
                f"{float(r.get('igst') or 0):,.2f}",
            ])
        tax_widths = [24 * mm, 44 * mm, 44 * mm]
    else:
        tax_head = ["GST%", f"Taxable ({currency})", f"GST ({currency})"]
        tax_rows = [tax_head]
        for r in data.get("tax_summary", []):
            tax_rows.append([
                f"{float(r.get('rate', 0)):.0f}%",
                f"{float(r.get('taxable', 0)):,.2f}",
                f"{float(r.get('total_tax', 0)):,.2f}",
            ])
        tax_widths = [24 * mm, 44 * mm, 44 * mm]

    if len(tax_rows) > 1:
        tax_tbl = Table(tax_rows, colWidths=tax_widths)
        tax_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#444444")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ]))
        elems.append(tax_tbl)
        elems.append(Spacer(1, 10))

    # Totals box
    t = data.get("totals", {})
    totals_rows = [
        ["Subtotal", _fmt_money(currency, t.get("subtotal_amount", 0))],
        ["Discount", "- " + _fmt_money(currency, t.get("discount_amount", 0))],
        ["Tax", _fmt_money(currency, t.get("tax_amount", 0))],
        ["Shipping", _fmt_money(currency, t.get("shipping_amount", 0))],
        ["Grand Total", _fmt_money(currency, t.get("total_amount", 0))],
    ]
    totals_tbl = Table(totals_rows, colWidths=[34 * mm, 40 * mm], hAlign="RIGHT")
    totals_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.black),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, -1), (-1, -1), BRAND_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elems.append(totals_tbl)
    elems.append(Spacer(1, 16))

    # Footer
    elems.append(Paragraph(
        "This is a computer-generated invoice and does not require a signature.",
        ParagraphStyle("footer", parent=small, textColor=colors.grey, alignment=1),
    ))

    doc.build(elems)
    pdf = buf.getvalue()
    buf.close()
    return pdf
