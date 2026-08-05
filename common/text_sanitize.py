"""
Plain-text sanitisation + validation helpers for user-authored profile text.

Used by the merchant bio (and reusable for any other short public text field).
The rule everywhere is: these fields are PLAIN TEXT. They are never rendered as
HTML, so we strip markup rather than trying to allow-list it.
"""

import re
import unicodedata
from urllib.parse import urlparse

# Tags are stripped rather than escaped: the value is displayed as text, so a
# literal "<b>" the merchant typed would otherwise show up as "&lt;b&gt;".
_HTML_TAG_RE = re.compile(r'<[^>]*>')
_CARRIAGE_RETURN_RE = re.compile(r'\r\n?')
_EXCESS_NEWLINES_RE = re.compile(r'\n{3,}')

ALLOWED_URL_SCHEMES = ('http', 'https')


def sanitize_plain_text(value, allow_newlines=True):
    """
    Normalise user-authored plain text.

    - strips HTML tags
    - normalises CRLF/CR to LF
    - collapses 3+ consecutive newlines to 2
    - removes control and format characters (Cc/Cf) except newline; this also
      removes zero-width joiners/spaces and RTL-override characters used to
      spoof display text
    - trims surrounding whitespace

    Returns None for values that are empty after sanitisation, so callers can
    treat "cleared" and "never set" identically.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)

    value = _HTML_TAG_RE.sub('', value)
    value = _CARRIAGE_RETURN_RE.sub('\n', value)

    cleaned = []
    for char in value:
        if char == '\n':
            if allow_newlines:
                cleaned.append(char)
            else:
                cleaned.append(' ')
            continue
        if unicodedata.category(char) in ('Cc', 'Cf'):
            continue
        cleaned.append(char)
    value = ''.join(cleaned)

    if allow_newlines:
        value = _EXCESS_NEWLINES_RE.sub('\n\n', value)
        # Trim trailing spaces on each line so the counter matches what shows.
        value = '\n'.join(line.rstrip() for line in value.split('\n'))

    value = value.strip()
    return value or None


def validate_text_length(value, field_name, max_chars, max_lines=None):
    """
    Return a list of error strings (empty when valid).

    Length is measured in characters, never bytes — an emoji is one character
    to the merchant typing it and must be one character here too.
    """
    errors = []
    if value is None:
        return errors
    if len(value) > max_chars:
        errors.append(
            f"{field_name} must be {max_chars} characters or fewer (got {len(value)})."
        )
    if max_lines is not None and value.count('\n') + 1 > max_lines:
        errors.append(f"{field_name} must be {max_lines} lines or fewer.")
    return errors


def sanitize_url(value, max_length=512):
    """
    Validate and normalise a user-supplied link.

    Returns (url_or_None, error_or_None). Only http/https are accepted —
    javascript:, data: and vbscript: URIs are the classic stored-XSS vector for
    a "link in bio" field.
    """
    if value is None:
        return None, None
    if not isinstance(value, str):
        value = str(value)

    value = value.strip()
    if not value:
        return None, None

    if len(value) > max_length:
        return None, f"Link must be {max_length} characters or fewer."

    # Be forgiving about a missing scheme, the way social apps are.
    if '://' not in value:
        value = f'https://{value}'

    try:
        parsed = urlparse(value)
    except ValueError:
        return None, "Link is not a valid URL."

    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
        return None, "Link must start with http:// or https://."
    if not parsed.netloc or '.' not in parsed.netloc:
        return None, "Link is not a valid URL."

    return value, None
