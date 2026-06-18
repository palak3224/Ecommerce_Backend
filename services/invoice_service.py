# services/invoice_service.py
"""Assemble invoice data for a customer order (GST tax invoice, combined / multi-merchant).

Design goals:
- Never raise on missing optional data — every field has a safe fallback so an
  invoice can always be produced for a valid, paid order.
- Compute the CGST/SGST vs IGST split from seller-state vs buyer-state when both
  are known; otherwise fall back to a single combined GST line.
- Pure data assembly: no PDF, no Flask response. Returns a plain dict.
"""
from decimal import Decimal, ROUND_HALF_UP

from models.order import Order, OrderItem
from models.enums import PaymentStatusEnum

# Result of build_invoice_data is a dict; these statuses are considered "paid".
PAID_PAYMENT_STATUSES = {PaymentStatusEnum.SUCCESSFUL, PaymentStatusEnum.PARTIALLY_REFUNDED, PaymentStatusEnum.REFUNDED}


class InvoiceError(Exception):
    """Raised with an (message, http_status) so the controller can map it cleanly."""

    def __init__(self, message, status):
        super().__init__(message)
        self.message = message
        self.status = status


def _money(value):
    """Coerce anything to a 2-dp Decimal, defaulting to 0.00."""
    if value is None:
        return Decimal("0.00")
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _norm_state(value):
    """Normalize a state name for comparison (lowercase, trimmed)."""
    return (value or "").strip().lower()


def _address_dict(addr):
    """Serialize a UserAddress (or None) to a safe dict for the invoice."""
    if not addr:
        return None
    parts = [addr.address_line1, addr.address_line2, addr.landmark]
    line = ", ".join(p for p in parts if p)
    return {
        "contact_name": addr.contact_name or "",
        "contact_phone": addr.contact_phone or "",
        "address_line": line,
        "city": addr.city or "",
        "state_province": addr.state_province or "",
        "postal_code": addr.postal_code or "",
        "country_code": addr.country_code or "",
    }


def _seller_block(order):
    """Derive a single seller block from the order's items.

    Combined invoices may contain multiple merchants; for the header we use the
    first merchant found and flag multi-seller so the PDF can note it. Each line
    item still records its own merchant name.
    """
    merchants = []
    seen = set()
    for item in order.items:
        m = getattr(item, "merchant", None)
        if m and m.id not in seen:
            seen.add(m.id)
            merchants.append(m)
    primary = merchants[0] if merchants else None
    return {
        "primary": {
            "business_name": (primary.business_name if primary else "") or "Seller",
            "address": (primary.business_address if primary else "") or "",
            "city": (primary.city if primary else "") or "",
            "state_province": (primary.state_province if primary else "") or "",
            "gstin": (primary.gstin if primary else "") or "",
            "pan_number": (primary.pan_number if primary else "") or "",
        },
        "multi_seller": len(merchants) > 1,
        "seller_count": len(merchants),
        "_primary_state": _norm_state(primary.state_province if primary else None),
    }


def build_invoice_data(order_id, user_id, require_paid=True):
    """Build the invoice data dict for an order owned by user_id.

    Raises InvoiceError(message, status) on not-found (404), not-owner (403),
    or not-paid (400 when require_paid). Otherwise returns a dict consumable by
    the PDF renderer.
    """
    order = Order.query.options(
        # items + each item's merchant; addresses are lazy='joined' on the model already
    ).get(order_id)

    if not order:
        raise InvoiceError("Order not found", 404)

    # Ownership: the order must belong to the requesting user.
    if order.user_id is None or int(order.user_id) != int(user_id):
        raise InvoiceError("You are not allowed to view this invoice", 403)

    if require_paid and order.payment_status not in PAID_PAYMENT_STATUSES:
        raise InvoiceError("Invoice is available only after successful payment", 400)

    seller = _seller_block(order)
    billing = _address_dict(order.billing_address_obj) or _address_dict(order.shipping_address_obj)
    shipping = _address_dict(order.shipping_address_obj)

    # Decide intra-state vs inter-state for the GST split.
    # Intra-state (seller state == buyer state) -> CGST + SGST; else -> IGST.
    # If either state is unknown, fall back to a single combined GST line.
    buyer_state = _norm_state((billing or {}).get("state_province"))
    seller_state = seller["_primary_state"]
    if seller_state and buyer_state:
        is_intra_state = seller_state == buyer_state
        split_known = True
    else:
        is_intra_state = False
        split_known = False  # -> render a single "GST" column instead of CGST/SGST/IGST

    # Build line items + per-rate tax aggregation.
    line_items = []
    tax_by_rate = {}  # rate(Decimal) -> {"taxable": Decimal, "tax": Decimal}
    total_taxable = Decimal("0.00")
    total_tax = Decimal("0.00")

    for idx, item in enumerate(order.items, start=1):
        qty = item.quantity or 0
        gst_rate = _money(item.gst_rate_applied_at_purchase)
        gst_per_unit = _money(item.gst_amount_per_unit)
        line_total_incl = _money(item.line_item_total_inclusive_gst)
        line_tax = (gst_per_unit * Decimal(qty)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        line_taxable = (line_total_incl - line_tax).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if line_taxable < 0:
            line_taxable = Decimal("0.00")

        merchant_name = ""
        m = getattr(item, "merchant", None)
        if m and m.business_name:
            merchant_name = m.business_name

        line_items.append({
            "sl": idx,
            "name": item.product_name_at_purchase or "Item",
            "sku": item.sku_at_purchase or "",
            "merchant_name": merchant_name,
            "quantity": qty,
            "gst_rate": gst_rate,
            "taxable_value": line_taxable,
            "tax_amount": line_tax,
            "line_total": line_total_incl,
        })

        key = str(gst_rate)
        bucket = tax_by_rate.setdefault(key, {"rate": gst_rate, "taxable": Decimal("0.00"), "tax": Decimal("0.00")})
        bucket["taxable"] += line_taxable
        bucket["tax"] += line_tax
        total_taxable += line_taxable
        total_tax += line_tax

    # Build the tax summary rows with CGST/SGST/IGST split when known.
    tax_summary = []
    for key in sorted(tax_by_rate.keys(), key=lambda k: float(k)):
        b = tax_by_rate[key]
        row = {
            "rate": b["rate"],
            "taxable": b["taxable"].quantize(Decimal("0.01")),
            "total_tax": b["tax"].quantize(Decimal("0.01")),
        }
        if split_known and is_intra_state:
            half = (b["tax"] / Decimal("2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            row["cgst"] = half
            row["sgst"] = (b["tax"] - half).quantize(Decimal("0.01"))
            row["igst"] = None
        elif split_known and not is_intra_state:
            row["cgst"] = None
            row["sgst"] = None
            row["igst"] = b["tax"].quantize(Decimal("0.01"))
        else:
            row["cgst"] = None
            row["sgst"] = None
            row["igst"] = None
        tax_summary.append(row)

    # Tax mode label drives the PDF columns.
    if not split_known:
        tax_mode = "GST"
    elif is_intra_state:
        tax_mode = "CGST_SGST"
    else:
        tax_mode = "IGST"

    order_date = order.order_date
    return {
        "invoice_number": f"INV-{order.order_id}",
        "order_id": order.order_id,
        "order_date": order_date,
        "currency": order.currency or "INR",
        "payment_method": order.payment_method.value if order.payment_method else "",
        "payment_status": order.payment_status.value if order.payment_status else "",
        "seller": seller["primary"],
        "multi_seller": seller["multi_seller"],
        "buyer_billing": billing,
        "buyer_shipping": shipping,
        "line_items": line_items,
        "tax_mode": tax_mode,
        "tax_summary": tax_summary,
        "totals": {
            "taxable_value": total_taxable.quantize(Decimal("0.01")),
            "tax_total": total_tax.quantize(Decimal("0.01")),
            "subtotal_amount": _money(order.subtotal_amount),
            "discount_amount": _money(order.discount_amount),
            "shipping_amount": _money(order.shipping_amount),
            "tax_amount": _money(order.tax_amount),
            "total_amount": _money(order.total_amount),
        },
    }
