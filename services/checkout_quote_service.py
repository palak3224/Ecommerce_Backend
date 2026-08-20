# services/checkout_quote_service.py
"""The one place a basket total is computed.

The rule this file exists to enforce: **the client names intent, the server names
money.** A request may say "product 7, quantity 2, promo code SUMMER10". It may not
say "that costs 1299.00" — every amount below is read from the database or derived
from it.

The arithmetic mirrors OrderController.create_order exactly (same Decimal ops, same
ROUND_HALF_UP quantize, same GST back-calculation) because a quote that disagrees
with the order it becomes is worse than no quote. Materialising an order from a
quote is a straight copy of the stored line items, so the two cannot drift.

INR only. Invariant I6: GST slab selection is fed the INR listed price, never a
converted one.
"""
from datetime import datetime, date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import json

from flask import current_app

from common.database import db
from models.checkout_quote import CheckoutQuote, CheckoutQuoteItem, QuoteStatus
from models.enums import DiscountType
from models.gst_rule import GSTRule
from models.product import Product
from models.product_stock import ProductStock
from models.promotion import Promotion
from services.fx_service import to_presentment, FxError


TWO_PLACES = Decimal("0.01")


class QuoteError(ValueError):
    """A basket the server refuses to price. The message is user-facing."""


def _q(value):
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def minor_units(amount, currency="INR"):
    """Decimal major units -> integer minor units.

    Imported by the payment routes so the integer the gateway is asked to charge and
    the integer stored on the quote come from one implementation.
    """
    # Local import: routes.razorpay_routes imports this module, so importing it at
    # module scope would close the cycle.
    from routes.razorpay_routes import minor_unit_factor

    factor = minor_unit_factor(currency)
    return int((Decimal(amount) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _resolve_promotion(code, now=None):
    """Look a promo code up. Returns a Promotion or None; never trusts an amount."""
    if not code:
        return None
    today = (now or datetime.utcnow()).date()
    # .upper() to match POST /api/promo-code/apply, which uppercases before looking
    # up. Without it a customer who typed a lowercase code would be shown a discount
    # by that endpoint and then not get it in the quote.
    promo = Promotion.query.filter(
        Promotion.code == str(code).strip().upper(),
        Promotion.active_flag.is_(True),
        Promotion.deleted_at.is_(None),
    ).first()
    if not promo:
        return None
    if promo.start_date and today < promo.start_date:
        return None
    if promo.end_date and today > promo.end_date:
        return None
    return promo


def _promotion_applies_to(promo, product):
    """A promo with no target applies basket-wide; a targeted one must match."""
    if promo.product_id is not None:
        return promo.product_id == product.product_id
    if promo.category_id is not None:
        return promo.category_id == product.category_id
    if promo.brand_id is not None:
        return promo.brand_id == product.brand_id
    return True


def _resolve_line_discounts(promo, entries):
    """Server-computed discount per *line*, mirroring POST /api/promo-code/apply.

    Replaces the client-supplied `item_discount_inclusive` that create_order used to
    accept verbatim — a field the browser could set to any value it liked.

    These semantics are not a free choice: they must match the promo endpoint,
    because that endpoint is what quoted the discount to the customer before they
    reached checkout. A different number here either overcharges against the total
    they were shown, or hands out money.

      sitewide + fixed      -> the value ONCE across the basket, spread pro rata
      sitewide + percentage -> the percentage on every line
      targeted + fixed      -> min(line_total, value) on each matching line
      targeted + percentage -> the percentage on each matching line

    `entries` carries `product`, `quantity` and `line_total` per line. Returns a
    list of Decimal line discounts, index-aligned with `entries`.
    """
    zero = [Decimal("0.00") for _ in entries]
    if promo is None or not entries:
        return zero

    is_sitewide = (
        promo.product_id is None
        and promo.category_id is None
        and promo.brand_id is None
    )
    value = Decimal(promo.discount_value)
    is_pct = promo.discount_type == DiscountType.PERCENTAGE
    if is_pct:
        # A percentage over 100 would invert the price; clamp rather than trust.
        value = min(max(value, Decimal("0")), Decimal("100"))
    else:
        value = max(value, Decimal("0"))

    basket_total = sum(e["line_total"] for e in entries)

    if is_sitewide and not is_pct:
        # One fixed amount for the whole basket, never more than the basket itself,
        # distributed in proportion to each line.
        if basket_total <= Decimal("0.00"):
            return zero
        to_apply = min(basket_total, value)
        return [_q(to_apply * (e["line_total"] / basket_total)) for e in entries]

    out = []
    for e in entries:
        if not (is_sitewide or _promotion_applies_to(promo, e["product"])):
            out.append(Decimal("0.00"))
        elif is_pct:
            out.append(_q(e["line_total"] * value / Decimal("100")))
        else:
            # Capped at the line, so a fixed discount can never make a line negative
            # and drag the basket total down.
            out.append(_q(min(e["line_total"], value)))
    return out


def _resolve_shipping(subtotal_inclusive):
    """Shipping is server-side too — the client used to state it outright.

    Defaults to zero, which is what the marketplace charges today. The config keys
    are the seam for real rate-card / ShipRocket serviceability work; they are read
    here so that when they are set, no other code has to change.
    """
    flat = Decimal(str(current_app.config.get("DEFAULT_SHIPPING_AMOUNT", "0.00")))
    threshold = current_app.config.get("FREE_SHIPPING_THRESHOLD")
    if threshold is not None and subtotal_inclusive >= Decimal(str(threshold)):
        return Decimal("0.00")
    return _q(flat)


def _basket_from_request(user_id, payload):
    """Normalise the requested basket to [(product_id, quantity, attributes)].

    Accepts explicit items, or falls back to the user's server-side cart. Quantities
    are the only numbers taken from the caller, and they are bounded.
    """
    raw_items = payload.get("items")

    if not raw_items:
        from models.cart import Cart, CartItem

        cart = Cart.query.filter_by(user_id=user_id, is_deleted=False).first()
        if not cart:
            raise QuoteError("Cart is empty.")
        rows = CartItem.query.filter_by(cart_id=cart.cart_id, is_deleted=False).all()
        raw_items = [
            {
                "product_id": r.product_id,
                "quantity": r.quantity,
                "selected_attributes": r.get_selected_attributes(),
            }
            for r in rows
        ]

    if not raw_items:
        raise QuoteError("Cart is empty.")

    basket = []
    for item in raw_items:
        try:
            product_id = int(item["product_id"])
            quantity = int(item["quantity"])
        except (KeyError, TypeError, ValueError):
            raise QuoteError("Each item needs a numeric product_id and quantity.")
        if quantity <= 0:
            raise QuoteError("Quantity must be greater than zero.")
        if quantity > 1000:
            raise QuoteError("Quantity exceeds the per-item limit.")
        basket.append((product_id, quantity, item.get("selected_attributes") or {}))

    return basket


def price_basket(user_id, payload, now=None):
    """Price a basket server-side. Returns (totals_dict, [line_dicts]).

    Pure with respect to the database: reads products, GST rules, stock and
    promotions, writes nothing. build_quote persists what this returns.
    """
    now = now or datetime.utcnow()
    basket = _basket_from_request(user_id, payload)
    promo = _resolve_promotion(payload.get("promo_code"), now=now)

    # First pass: resolve products and list prices. Discounts cannot be computed
    # per item in isolation — a sitewide fixed promo is one amount spread across the
    # whole basket — so the basket has to be fully known before any of it is applied.
    entries = []
    for product_id, quantity, attributes in basket:
        product = Product.query.get(product_id)
        if not product or product.deleted_at is not None:
            # Named rather than silently dropped: a basket that quietly loses a line
            # would be quoted for less than the customer thinks they are buying.
            raise QuoteError(
                f"{product.product_name if product else f'Product {product_id}'} "
                f"is no longer available. Please remove it from your basket."
            )

        listed_inclusive_per_unit, _ = product.get_current_listed_inclusive_price()
        listed_inclusive_per_unit = _q(listed_inclusive_per_unit)

        entries.append({
            "product": product,
            "quantity": quantity,
            "attributes": attributes,
            "listed_per_unit": listed_inclusive_per_unit,
            "line_total": _q(listed_inclusive_per_unit * quantity),
        })

    line_discounts = _resolve_line_discounts(promo, entries)

    lines = []
    total_base = Decimal("0.00")
    total_gst = Decimal("0.00")
    total_discount = Decimal("0.00")

    # Second pass: price each line off its share of the discount.
    for entry, line_discount in zip(entries, line_discounts):
        product = entry["product"]
        quantity = entry["quantity"]
        attributes = entry["attributes"]
        listed_inclusive_per_unit = entry["listed_per_unit"]

        # Store per unit, mirroring OrderItem. Rounding the per-unit figure and then
        # multiplying back keeps Sigma(lines) exact (I5).
        #
        # ROUND_DOWN, not HALF_UP: a 50.00 promo over 3 units is 16.6666... per unit,
        # and rounding half-up gives 16.67 x 3 = 50.01 — a paise more discount than
        # the promotion actually grants. Rounding down means the customer can lose at
        # most (quantity - 1) paise and can never gain any, so a discount never
        # exceeds its own value.
        discount_per_unit = (
            (line_discount / quantity).quantize(TWO_PLACES, rounding=ROUND_DOWN)
            if quantity else Decimal("0.00")
        )
        discount_per_unit = min(discount_per_unit, listed_inclusive_per_unit)

        pays_per_unit = listed_inclusive_per_unit - discount_per_unit
        if pays_per_unit < Decimal("0.00"):
            pays_per_unit = Decimal("0.00")

        # I6: the slab is chosen from the INR *listed* price, not the discounted or
        # converted one, so a discount can never move an item into a lower GST band.
        rule = GSTRule.find_applicable_rule(
            db_session=db.session,
            product_category_id=product.category_id,
            product_inclusive_price=listed_inclusive_per_unit,
        )
        gst_rate = Decimal(rule.gst_rate_percentage) if rule else Decimal("0.00")

        denominator = Decimal("1.00") + (gst_rate / Decimal("100.00"))
        if denominator > Decimal("0.00"):
            base_per_unit = _q(pays_per_unit / denominator)
            gst_per_unit = _q(pays_per_unit - base_per_unit)
        else:
            base_per_unit = pays_per_unit
            gst_per_unit = Decimal("0.00")

        stock = ProductStock.query.filter_by(product_id=product.product_id).first()
        if not stock:
            raise QuoteError(f"Stock record not found for {product.product_name}.")
        if stock.stock_qty < quantity:
            raise QuoteError(
                f"Insufficient stock for {product.product_name}. "
                f"Available: {stock.stock_qty}, requested: {quantity}"
            )

        lines.append(
            {
                "product_id": product.product_id,
                "merchant_id": product.merchant_id,
                "quantity": quantity,
                "product_name_at_purchase": product.product_name,
                "sku_at_purchase": product.sku,
                "original_listed_inclusive_price_per_unit": _q(listed_inclusive_per_unit),
                "discount_amount_per_unit_applied": discount_per_unit,
                "unit_price_inclusive_gst": _q(pays_per_unit),
                "final_base_price_for_gst_calc": base_per_unit,
                "gst_rate_applied_at_purchase": gst_rate,
                "gst_amount_per_unit": gst_per_unit,
                "line_item_total_inclusive_gst": _q(pays_per_unit * quantity),
                "selected_attributes": json.dumps(attributes),
            }
        )

        total_base += base_per_unit * quantity
        total_gst += gst_per_unit * quantity
        total_discount += discount_per_unit * quantity

    lines_total = sum(l["line_item_total_inclusive_gst"] for l in lines)
    shipping = _resolve_shipping(lines_total)
    total = _q(lines_total + shipping)

    totals = {
        "subtotal_amount": _q(total_base),
        "tax_amount": _q(total_gst),
        "discount_amount": _q(total_discount),
        "shipping_amount": shipping,
        "total_amount": total,
        "currency": current_app.config.get("DEFAULT_CURRENCY", "INR"),
    }

    # I5, checked here rather than trusted: the parts must reconstruct the total
    # exactly. A mismatch means the arithmetic above drifted and must not reach a
    # payment gateway.
    reconstructed = _q(sum(l["line_item_total_inclusive_gst"] for l in lines) + shipping)
    if reconstructed != totals["total_amount"]:
        raise QuoteError("Internal pricing error: basket total did not reconcile.")

    return totals, lines


def _compute_presentment(totals, requested_currency, on_date=None):
    """Derive the presentment (charge) amounts for a quote in `requested_currency`.

    Returns a dict of presentment amounts + `fx_rate_id`, or None. None means "charge
    in the book currency (INR)" and is the safe answer for every reason a conversion
    should not happen: multi-currency off, no/blank currency requested, the request is
    already the book currency, an unsupported currency, or no usable FX rate. The book
    (INR) columns on the quote are never touched.
    """
    base = current_app.config.get("DEFAULT_CURRENCY", "INR")
    requested = (requested_currency or "").upper()

    if not current_app.config.get("FEATURE_MULTI_CURRENCY", False):
        return None
    if not requested or requested == base.upper():
        return None

    supported = {c.strip().upper() for c in
                 (current_app.config.get("FX_QUOTE_CURRENCIES") or "").split(",") if c.strip()}
    if requested not in supported:
        current_app.logger.info("Quote: unsupported presentment currency %s ignored", requested)
        return None

    try:
        # The grand total is the authoritative charge amount: one conversion, with
        # markup and marketing rounding, so the customer pays a clean figure.
        pres_total, rate_row = to_presentment(totals["total_amount"], requested, base, on_date=on_date)
        # Components carry no marketing rounding; they exist for the invoice/breakdown
        # and are reconciled to the charged total below.
        sub, _ = to_presentment(totals["subtotal_amount"], requested, base, on_date=on_date, marketing_rounding=False)
        tax, _ = to_presentment(totals["tax_amount"], requested, base, on_date=on_date, marketing_rounding=False)
        disc, _ = to_presentment(totals["discount_amount"], requested, base, on_date=on_date, marketing_rounding=False)
        ship, _ = to_presentment(totals["shipping_amount"], requested, base, on_date=on_date, marketing_rounding=False)
    except FxError as e:
        # No usable rate → charge INR rather than break checkout (docs, Phase 7:
        # "with the flag on and no rates, every presentment falls back to INR").
        current_app.logger.warning(
            "Quote: FX unavailable for %s, charging in %s instead. %s", requested, base, e
        )
        return None

    # I5: subtotal + tax - discount + shipping must reconstruct the charged total
    # exactly. The rounding residual (a cent or two) is absorbed into the subtotal.
    residual = _q(pres_total) - _q(sub + tax - disc + ship)
    sub = _q(sub + residual)

    return {
        "currency": requested,
        "subtotal_amount": _q(sub),
        "tax_amount": _q(tax),
        "discount_amount": _q(disc),
        "shipping_amount": _q(ship),
        "total_amount": _q(pres_total),
        "total_minor": minor_units(_q(pres_total), requested),
        "fx_rate_id": rate_row.fx_rate_id if rate_row else None,
    }


def build_quote(user_id, payload, now=None):
    """Price a basket and persist it as a spendable quote."""
    now = now or datetime.utcnow()
    totals, lines = price_basket(user_id, payload, now=now)

    if totals["total_amount"] <= Decimal("0.00"):
        raise QuoteError("Basket total must be greater than zero.")

    # Presentment (Phase 7): if the customer is browsing in a supported non-INR
    # currency and the flag is on, derive what they are charged in that currency.
    presentment = _compute_presentment(
        totals, payload.get("presentment_currency"),
        on_date=now.date() if hasattr(now, "date") else None,
    )

    quote = CheckoutQuote(
        user_id=user_id,
        status=QuoteStatus.ACTIVE,
        currency=totals["currency"],
        subtotal_amount=totals["subtotal_amount"],
        discount_amount=totals["discount_amount"],
        tax_amount=totals["tax_amount"],
        shipping_amount=totals["shipping_amount"],
        total_amount=totals["total_amount"],
        total_amount_minor=minor_units(totals["total_amount"], totals["currency"]),
        presentment_currency=presentment["currency"] if presentment else None,
        presentment_subtotal_amount=presentment["subtotal_amount"] if presentment else None,
        presentment_discount_amount=presentment["discount_amount"] if presentment else None,
        presentment_tax_amount=presentment["tax_amount"] if presentment else None,
        presentment_shipping_amount=presentment["shipping_amount"] if presentment else None,
        presentment_total_amount=presentment["total_amount"] if presentment else None,
        presentment_total_minor=presentment["total_minor"] if presentment else None,
        fx_rate_id=presentment["fx_rate_id"] if presentment else None,
        shipping_address_id=payload.get("shipping_address_id"),
        billing_address_id=payload.get("billing_address_id"),
        shipping_method_name=payload.get("shipping_method_name"),
        created_at=now,
        expires_at=CheckoutQuote.default_expiry(now),
    )
    for line in lines:
        quote.items.append(CheckoutQuoteItem(**line))

    db.session.add(quote)
    db.session.commit()
    return quote


def load_spendable_quote(quote_id, user_id, now=None):
    """Fetch a quote that may still be paid against, or raise QuoteError.

    Deliberately does not mutate: expiry is reported, not written, so that a read
    never races a concurrent consume. consume_quote does the state change.
    """
    now = now or datetime.utcnow()
    if not quote_id:
        raise QuoteError("quote_id is required.")

    quote = CheckoutQuote.query.get(str(quote_id))
    if not quote or quote.user_id != user_id:
        # Same message either way: whether a quote id exists is not the caller's
        # business if it is not theirs.
        raise QuoteError("Quote not found.")
    if quote.status == QuoteStatus.CONSUMED:
        raise QuoteError("This quote has already been paid.")
    if quote.status != QuoteStatus.ACTIVE:
        raise QuoteError(f"Quote is {quote.status.lower()}.")
    if quote.is_expired(now):
        raise QuoteError("Quote has expired. Please refresh your basket.")
    return quote


def consume_quote(quote_id, order_id=None, now=None):
    """Atomically mark a quote spent. Returns True only for the caller that won.

    A conditional UPDATE, not read-then-write: the WHERE clause carries the
    precondition, so two concurrent captures against one quote cannot both proceed
    regardless of isolation level or backend. This is invariant I10.
    """
    now = now or datetime.utcnow()
    updated = (
        db.session.query(CheckoutQuote)
        .filter(
            CheckoutQuote.quote_id == str(quote_id),
            CheckoutQuote.status == QuoteStatus.ACTIVE,
        )
        .update(
            {
                CheckoutQuote.status: QuoteStatus.CONSUMED,
                CheckoutQuote.consumed_at: now,
                CheckoutQuote.order_id: order_id,
            },
            synchronize_session=False,
        )
    )
    return updated == 1
