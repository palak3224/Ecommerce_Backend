"""Refund ledger invariants (docs/MULTI_CURRENCY.md, invariant I11).

Scope note: these cover the ledger itself — that refunds are persisted, summed, and
denominated in the capture's currency. The over-refund *guard* lives in the route
and calls the gateway, so it is exercised here through the same summing function the
route uses rather than through a mocked Razorpay client.
"""
import pytest

from app import create_app
from common.database import db


@pytest.fixture
def app():
    application = create_app("testing")
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


def _refund(payment_id, minor, currency="INR", status=None):
    from models.payment_refund import PaymentRefund, RefundStatus
    r = PaymentRefund(
        gateway_payment_id=payment_id,
        amount_minor=minor,
        currency=currency,
        status=status or RefundStatus.PROCESSED,
    )
    db.session.add(r)
    db.session.commit()
    return r


def test_refund_is_persisted(app):
    """Before this table a refund left no trace in our own database at all."""
    from models.payment_refund import PaymentRefund

    with app.app_context():
        rid = _refund("pay_1", 5000).refund_id
        db.session.expunge_all()

        fresh = PaymentRefund.query.get(rid)
        assert fresh.amount_minor == 5000
        assert fresh.currency == "INR"
        assert fresh.gateway_payment_id == "pay_1"


def test_partial_refunds_sum(app):
    from models.payment_refund import PaymentRefund

    with app.app_context():
        _refund("pay_2", 3000)
        _refund("pay_2", 2500)
        assert PaymentRefund.total_refunded_minor("pay_2") == 5500


def test_failed_refunds_do_not_count_against_the_capture(app):
    """A failed attempt must not consume refundable headroom."""
    from models.payment_refund import PaymentRefund, RefundStatus

    with app.app_context():
        _refund("pay_3", 4000, status=RefundStatus.PROCESSED)
        _refund("pay_3", 9999, status=RefundStatus.FAILED)
        assert PaymentRefund.total_refunded_minor("pay_3") == 4000


def test_over_refund_is_detectable(app):
    """The check the route performs: already + requested must not exceed captured."""
    from models.payment_refund import PaymentRefund

    with app.app_context():
        captured_minor = 10000
        _refund("pay_4", 6000)

        already = PaymentRefund.total_refunded_minor("pay_4")
        assert already + 4000 <= captured_minor      # exact remainder is allowed
        assert already + 4001 > captured_minor       # one minor unit more is not


def test_refunds_are_summed_per_payment(app):
    from models.payment_refund import PaymentRefund

    with app.app_context():
        _refund("pay_5", 1000)
        _refund("pay_6", 7000)
        assert PaymentRefund.total_refunded_minor("pay_5") == 1000
        assert PaymentRefund.total_refunded_minor("pay_6") == 7000
        assert PaymentRefund.total_refunded_minor("pay_unknown") == 0
