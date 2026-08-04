"""Turn database errors into messages a merchant/admin can act on.

The frontend can only show what the API sends back, so a blanket
"Failed to create product" hides the real cause (duplicate SKU, missing
category, NULL in a required column...). Any handler that writes to the DB
should pass the exception through `describe_integrity_error()` /
`safe_error_message()` and return that instead of a hardcoded string.
"""

import re
from http import HTTPStatus

# Column / constraint names -> how we phrase them to the user.
FIELD_LABELS = {
    'sku': 'SKU',
    'product_name': 'product name',
    'slug': 'slug',
    'email': 'email address',
    'phone': 'phone number',
    'username': 'username',
    'name': 'name',
    'code': 'code',
    'category_id': 'category',
    'brand_id': 'brand',
    'merchant_id': 'merchant',
    'product_id': 'product',
    'order_id': 'order',
    'shop_id': 'shop',
}

_DUPLICATE_RE = re.compile(r"Duplicate entry '(?P<value>.*?)' for key '(?P<key>[^']+)'")
_FK_CHILD_RE = re.compile(r'FOREIGN KEY \(`?(?P<column>[^`)]+)`?\)')
_NOT_NULL_RE = re.compile(r"Column '(?P<column>[^']+)' cannot be null")
_TOO_LONG_RE = re.compile(r"Data too long for column '(?P<column>[^']+)'")

# str(IntegrityError) appends the full statement + bound params; never show that.
_SQL_NOISE_RE = re.compile(r'\s*\[(SQL|parameters):.*', re.DOTALL)


def _label_for(raw):
    """'products.sku' / 'uq_products_sku' / 'sku' -> a human label."""
    if not raw:
        return None
    key = raw.split('.')[-1].strip('`"')
    if key in FIELD_LABELS:
        return FIELD_LABELS[key]
    # Strip the usual index decorations: uq_/ix_/idx_/fk_ prefix, _key/_uindex suffix.
    key = re.sub(r'^(uq|ix|idx|fk|unique)_', '', key)
    key = re.sub(r'_(key|uindex|unique|idx|index)$', '', key)
    for column, label in FIELD_LABELS.items():
        if key == column or key.endswith('_' + column):
            return label
    return key.replace('_', ' ') or None


def safe_error_message(error, limit=300):
    """Readable one-liner for an exception, with SQL/bound parameters stripped."""
    message = _SQL_NOISE_RE.sub('', str(error)).strip()
    if not message:
        message = type(error).__name__
    return message[:limit]


def describe_integrity_error(error, entity='record'):
    """Map a SQLAlchemy IntegrityError to (message, http_status).

    `entity` is what the row represents ('product', 'brand', ...) and is used
    to phrase the message.
    """
    detail = str(getattr(error, 'orig', None) or error)

    duplicate = _DUPLICATE_RE.search(detail)
    if duplicate:
        label = _label_for(duplicate.group('key')) or 'value'
        value = duplicate.group('value')
        return (
            f"A {entity} with {label} '{value}' already exists. "
            f"Please use a different {label}.",
            HTTPStatus.CONFLICT,
        )

    not_null = _NOT_NULL_RE.search(detail)
    if not_null:
        label = _label_for(not_null.group('column')) or not_null.group('column')
        return (f"{label.capitalize()} is required and cannot be empty.",
                HTTPStatus.BAD_REQUEST)

    too_long = _TOO_LONG_RE.search(detail)
    if too_long:
        label = _label_for(too_long.group('column')) or too_long.group('column')
        return (f"The value entered for {label} is too long. Please shorten it.",
                HTTPStatus.BAD_REQUEST)

    if 'Cannot delete or update a parent row' in detail:
        return (
            f"This {entity} is still in use by other records. Remove or reassign "
            f"them (e.g. products, promotions, tax rules) first.",
            HTTPStatus.CONFLICT,
        )

    if 'Cannot add or update a child row' in detail:
        fk = _FK_CHILD_RE.search(detail)
        label = _label_for(fk.group('column')) if fk else None
        if label:
            return (f"The selected {label} does not exist or is no longer available. "
                    f"Please choose a valid {label}.", HTTPStatus.BAD_REQUEST)
        return ("One of the selected related records does not exist. "
                "Please check your selections and try again.", HTTPStatus.BAD_REQUEST)

    return (f"The {entity} could not be saved because it conflicts with existing data: "
            f"{safe_error_message(error, limit=200)}",
            HTTPStatus.BAD_REQUEST)
