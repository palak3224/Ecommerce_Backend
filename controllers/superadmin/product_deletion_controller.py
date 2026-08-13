# controllers/superadmin/product_deletion_controller.py
"""Superadmin takedown of merchant products.

Deletion is **soft**, and has to be: `order_items` reference products, and a past
order must still render its lines. A hard delete would rewrite history.

Two things separate this from the merchant's own delete:

1. It records **who** removed the listing and **why**. `deleted_at` alone cannot
   tell a merchant whether they retired a product themselves or an admin took it
   down, and a listing that vanishes with no explanation becomes a support ticket.
2. It **notifies the merchant**, so the takedown is something they are told about
   rather than something they discover.

The SKU is released on takedown. `products.sku` is unique, so leaving it in place
would block the merchant from re-listing a corrected version under the same code —
and "create a new one" is exactly what we are asking them to do. Order lines keep
their own `sku_at_purchase` snapshot, so history is unaffected.
"""
from datetime import datetime, timezone

from flask import current_app

from common.database import db
from models.enums import NotificationType
from models.merchant_notification import MerchantNotification
from models.product import Product


MAX_BULK_DELETE = 200


class ProductDeletionError(ValueError):
    """A takedown the server refuses. The message is shown to the admin."""


def _release_sku(product):
    """Free the unique SKU so the merchant can re-list under the same code.

    Suffixed rather than cleared: the original stays legible for anyone auditing
    why a product disappeared, and `sku` is NOT NULL so it cannot simply be voided.
    """
    if not product.sku:
        return
    freed = f"{product.sku}__deleted_{product.product_id}"
    # String(50) — truncate from the left of the suffix rather than overflow.
    product.sku = freed[:50]


def _notify_merchants(notes):
    """Tell merchants their listings were taken down. Best effort, never fatal.

    Runs in its own transaction *after* the takedown has committed. An earlier
    version added these rows to the same session and wrapped the add() in
    try/except, which protected nothing: `session.add()` does not touch the
    database, so the failure surfaced at commit() outside the guard and rolled the
    whole takedown back. A notification the merchant does not receive is a nuisance;
    a takedown that silently fails is a product still on sale after an admin
    removed it.

    The realistic failure here is schema drift — `notification_type` is a MySQL
    ENUM, and adding a value to the Python enum does not alter the column, so an
    unmigrated database rejects the insert. See run_migrations.py.
    """
    if not notes:
        return
    try:
        for merchant_id, product_id, product_name, reason in notes:
            db.session.add(MerchantNotification(
                merchant_id=merchant_id,
                notification_type=NotificationType.PRODUCT_DELETED_BY_ADMIN,
                title="Product removed by admin",
                message=(
                    f"'{product_name}' was removed by the AOIN team. "
                    f"Reason: {reason}. "
                    f"Please correct the issue and create a new listing."
                ),
                related_entity_type="product",
                related_entity_id=product_id,
            ))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            "Product takedown succeeded but merchant notifications failed: %s",
            e, exc_info=True,
        )


def delete_products(product_ids, admin_user_id, reason):
    """Take down one or many products. Returns a per-id result summary.

    Partial success is reported rather than hidden: an admin selecting 40 products
    where 2 were already gone should see 38 removed and 2 skipped, not a blanket
    failure or a silent success.
    """
    if not product_ids:
        raise ProductDeletionError("No products selected.")

    ids = []
    for raw in product_ids:
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            raise ProductDeletionError(f"Invalid product id: {raw!r}")
    ids = list(dict.fromkeys(ids))   # de-dupe, keep order

    if len(ids) > MAX_BULK_DELETE:
        raise ProductDeletionError(
            f"Select at most {MAX_BULK_DELETE} products at a time "
            f"({len(ids)} selected)."
        )

    reason = (reason or "").strip()
    if not reason:
        # Required, because the merchant is told the reason verbatim. "Removed" with
        # no explanation is the outcome this feature exists to avoid.
        raise ProductDeletionError("A reason is required — the merchant is shown it.")
    if len(reason) > 500:
        reason = reason[:500]

    products = Product.query.filter(Product.product_id.in_(ids)).all()
    found = {p.product_id: p for p in products}

    deleted, skipped = [], []
    pending_notes = []
    now = datetime.now(timezone.utc)

    for pid in ids:
        product = found.get(pid)
        if product is None:
            skipped.append({"product_id": pid, "reason": "not found"})
            continue
        if product.deleted_at is not None:
            skipped.append({"product_id": pid, "reason": "already deleted"})
            continue

        product.deleted_at = now
        product.deleted_by_user_id = admin_user_id
        product.deleted_by_role = "admin"
        product.deletion_reason = reason
        # Belt and braces: every listing query should already exclude deleted rows,
        # but clearing the flag means even a query that forgot cannot surface it.
        product.active_flag = False
        _release_sku(product)
        # Collected, not written yet — notifications are sent only after the
        # takedown itself has committed.
        pending_notes.append(
            (product.merchant_id, product.product_id, product.product_name, reason)
        )

        deleted.append({
            "product_id": product.product_id,
            "product_name": product.product_name,
            "merchant_id": product.merchant_id,
        })

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error("Product takedown failed: %s", e, exc_info=True)
        raise ProductDeletionError("Could not remove the selected products.")

    current_app.logger.info(
        "Admin %s removed %s product(s), skipped %s. Reason: %s",
        admin_user_id, len(deleted), len(skipped), reason,
    )

    # After the commit above, so it cannot take the takedown down with it.
    _notify_merchants(pending_notes)

    return {
        "deleted": deleted,
        "skipped": skipped,
        "deleted_count": len(deleted),
        "skipped_count": len(skipped),
        "reason": reason,
    }
