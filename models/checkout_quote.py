# models/checkout_quote.py
"""Server-authoritative checkout quotes.

A quote is the server's own computation of what a basket costs. The browser may
*ask* for a quote, but it can no longer *state* an amount: `create-order` takes a
quote id, and `verify-payment` asserts that what the gateway captured equals what
the quote said.

Two properties matter and are load-bearing:

1. A quote stores fully-resolved line items, not just a total. Materialising an
   order is then a copy, never a recompute, so "quote total == order total" holds
   by construction instead of by two code paths agreeing.
2. `total_amount_minor` is the integer handed to the gateway. Comparing captured
   amounts as integers removes every rounding and float question from the assert.

Amounts here are INR, like every other money column in this codebase — see
docs/MULTI_CURRENCY.md section 3. `currency` is stored so that the Phase 7 USD work
has somewhere to put presentment without reinterpreting these columns.
"""
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from common.database import db


# Minutes a quote stays usable. Long enough to finish a Razorpay modal, short
# enough that a stale price cannot be paid against hours later.
QUOTE_TTL_MINUTES = 30


class QuoteStatus:
    """Plain string states — deliberately not a DB Enum.

    init_db.py's auto-migration fabricates `DEFAULT '<first enum value>'` for Enum
    columns it adds to existing tables. Keeping this a String means a future column
    addition here cannot silently stamp every row ACTIVE.
    """
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


def _new_quote_id():
    return uuid.uuid4().hex


class CheckoutQuote(db.Model):
    __tablename__ = "checkout_quotes"

    quote_id = db.Column(db.String(64), primary_key=True, default=_new_quote_id)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    status = db.Column(db.String(16), nullable=False, default=QuoteStatus.ACTIVE, index=True)

    # Book currency. INR today; never derived from anything the client sent.
    currency = db.Column(db.String(3), nullable=False, default="INR")

    subtotal_amount = db.Column(db.Numeric(12, 2), nullable=False)
    discount_amount = db.Column(db.Numeric(12, 2), nullable=False)
    tax_amount = db.Column(db.Numeric(12, 2), nullable=False)
    shipping_amount = db.Column(db.Numeric(12, 2), nullable=False)
    total_amount = db.Column(db.Numeric(12, 2), nullable=False)

    # The exact integer sent to the gateway, and the integer verify-payment compares
    # the capture against. Derived from total_amount at quote time, never recomputed.
    total_amount_minor = db.Column(db.BigInteger, nullable=False)

    # --- Presentment (Phase 7). Populated only when the customer is charged in a
    # currency other than the book currency (e.g. USD). The columns above stay INR;
    # these hold the derived amount actually charged. All nullable with NO default,
    # so historical rows and INR checkouts leave them empty (docs Landmine #1). ---
    presentment_currency = db.Column(db.String(3), nullable=True)
    presentment_subtotal_amount = db.Column(db.Numeric(12, 2), nullable=True)
    presentment_discount_amount = db.Column(db.Numeric(12, 2), nullable=True)
    presentment_tax_amount = db.Column(db.Numeric(12, 2), nullable=True)
    presentment_shipping_amount = db.Column(db.Numeric(12, 2), nullable=True)
    presentment_total_amount = db.Column(db.Numeric(12, 2), nullable=True)
    presentment_total_minor = db.Column(db.BigInteger, nullable=True)
    # References fx_rates.fx_rate_id (append-only, so the exact rate stays provable —
    # I4). Stored as a plain id, not a DB FK, to keep the additive migration trivial.
    fx_rate_id = db.Column(db.Integer, nullable=True)

    @property
    def charge_currency(self):
        """The currency actually charged: presentment if set, else the book currency."""
        return self.presentment_currency or self.currency

    @property
    def charge_amount_minor(self):
        """The integer minor-unit amount actually charged."""
        if self.presentment_total_minor is not None:
            return int(self.presentment_total_minor)
        return int(self.total_amount_minor)

    @property
    def is_presentment(self):
        return self.presentment_currency is not None

    shipping_address_id = db.Column(db.Integer, nullable=True)
    billing_address_id = db.Column(db.Integer, nullable=True)
    shipping_method_name = db.Column(db.String(100), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    # Set when the quote is spent. order_id is the proof of the one-quote-one-order
    # invariant (I10) and is what makes double-spend detectable after the fact.
    consumed_at = db.Column(db.DateTime, nullable=True)
    order_id = db.Column(db.String(50), nullable=True, index=True)

    # Correlation to the gateway. Stored on the quote because the quote exists
    # before the order does — this is what replaces the client-minted receipt that
    # matched no row (docs/MULTI_CURRENCY.md section 5, defect 3).
    razorpay_order_id = db.Column(db.String(100), nullable=True, index=True)

    items = db.relationship(
        "CheckoutQuoteItem",
        backref="quote",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def is_expired(self, now=None):
        return (now or datetime.utcnow()) >= self.expires_at

    def is_spendable(self, now=None):
        return self.status == QuoteStatus.ACTIVE and not self.is_expired(now)

    def serialize(self):
        # The top-level currency/amounts describe what the customer is CHARGED, so the
        # UI and the gateway agree. When presentment is set that is USD; otherwise it is
        # the INR book figure. The INR book values are always exposed under base_*.
        pres = self.is_presentment
        return {
            "quote_id": self.quote_id,
            "status": self.status,
            # Charge view (presentment if any, else base). Strings, not floats — I9.
            "currency": self.charge_currency,
            "subtotal_amount": str(self.presentment_subtotal_amount if pres else self.subtotal_amount),
            "discount_amount": str(self.presentment_discount_amount if pres else self.discount_amount),
            "tax_amount": str(self.presentment_tax_amount if pres else self.tax_amount),
            "shipping_amount": str(self.presentment_shipping_amount if pres else self.shipping_amount),
            "total_amount": str(self.presentment_total_amount if pres else self.total_amount),
            "total_amount_minor": self.charge_amount_minor,
            # Book (INR) view — always present, for records and reconciliation.
            "base_currency": self.currency,
            "base_total_amount": str(self.total_amount),
            "is_presentment": pres,
            "fx_rate_id": self.fx_rate_id,
            "expires_at": self.expires_at.isoformat() + "Z",
            "created_at": self.created_at.isoformat() + "Z",
            "items": [i.serialize() for i in self.items],
        }

    @staticmethod
    def default_expiry(now=None):
        return (now or datetime.utcnow()) + timedelta(minutes=QUOTE_TTL_MINUTES)


class CheckoutQuoteItem(db.Model):
    __tablename__ = "checkout_quote_items"

    quote_item_id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(
        db.String(64),
        db.ForeignKey("checkout_quotes.quote_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    product_id = db.Column(db.Integer, nullable=False)
    merchant_id = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    # Snapshotted so the order is a copy of the quote, not a re-derivation.
    # These mirror OrderItem's columns one-for-one on purpose.
    product_name_at_purchase = db.Column(db.String(255), nullable=False)
    sku_at_purchase = db.Column(db.String(50), nullable=True)
    original_listed_inclusive_price_per_unit = db.Column(db.Numeric(12, 2), nullable=False)
    discount_amount_per_unit_applied = db.Column(db.Numeric(12, 2), nullable=False)
    unit_price_inclusive_gst = db.Column(db.Numeric(12, 2), nullable=False)
    final_base_price_for_gst_calc = db.Column(db.Numeric(12, 2), nullable=False)
    gst_rate_applied_at_purchase = db.Column(db.Numeric(5, 2), nullable=False)
    gst_amount_per_unit = db.Column(db.Numeric(12, 2), nullable=False)
    line_item_total_inclusive_gst = db.Column(db.Numeric(12, 2), nullable=False)

    selected_attributes = db.Column(db.Text, nullable=True)

    def serialize(self):
        return {
            "product_id": self.product_id,
            "merchant_id": self.merchant_id,
            "quantity": self.quantity,
            "product_name": self.product_name_at_purchase,
            "unit_price_inclusive_gst": str(self.unit_price_inclusive_gst),
            "original_listed_inclusive_price_per_unit": str(
                self.original_listed_inclusive_price_per_unit
            ),
            "discount_amount_per_unit_applied": str(self.discount_amount_per_unit_applied),
            "gst_rate": str(self.gst_rate_applied_at_purchase),
            "gst_amount_per_unit": str(self.gst_amount_per_unit),
            "line_item_total_inclusive_gst": str(self.line_item_total_inclusive_gst),
        }
