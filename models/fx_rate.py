# models/fx_rate.py
"""Foreign exchange rates — an append-only ledger, not a cache.

Rows here are referenced by id from orders (Phase 1's `fx_rate_id`), so an order
captured last March must still resolve to the rate it was actually priced at.
That makes these rows immutable: invariant I4 says every `fx_rate_id` resolves to a
never-mutated row, and I12 says no read path re-converts a historical order.

If a rate is wrong, insert a corrected row for that date. Never UPDATE one — an
order that already referenced it would silently change value.

The unique constraint is what enforces "one rate per pair per day per source", so a
job that runs twice cannot produce two competing answers for the same day.
"""
from datetime import datetime

from common.database import db


class FxRate(db.Model):
    __tablename__ = "fx_rates"

    fx_rate_id = db.Column(db.Integer, primary_key=True)

    base_currency = db.Column(db.String(3), nullable=False)
    quote_currency = db.Column(db.String(3), nullable=False)

    # Units of quote per 1 unit of base. INR->USD is ~0.0105, so this needs far more
    # than 2 decimal places; 12 keeps a cent accurate on any realistic basket.
    rate = db.Column(db.Numeric(20, 12), nullable=False)

    as_of_date = db.Column(db.Date, nullable=False)
    source = db.Column(db.String(50), nullable=False)

    fetched_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint(
            "base_currency", "quote_currency", "as_of_date", "source",
            name="uq_fx_rate_pair_day_source",
        ),
        db.Index("ix_fx_rate_lookup", "base_currency", "quote_currency", "as_of_date"),
    )

    def serialize(self):
        return {
            "fx_rate_id": self.fx_rate_id,
            "base_currency": self.base_currency,
            "quote_currency": self.quote_currency,
            # String, not float — invariant I9. A float here defeats the whole point
            # of storing 12 decimal places.
            "rate": str(self.rate),
            "as_of_date": self.as_of_date.isoformat(),
            "source": self.source,
            "fetched_at": self.fetched_at.isoformat() + "Z",
        }

    def __repr__(self):
        return (
            f"<FxRate {self.base_currency}->{self.quote_currency} "
            f"{self.rate} @ {self.as_of_date} ({self.source})>"
        )
