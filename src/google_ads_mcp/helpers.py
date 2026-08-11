"""Small pure utilities shared across tool modules."""

from __future__ import annotations

import re


def normalize_customer_id(customer_id: str) -> str:
    """Return a bare digits-only customer ID.

    Google Ads accepts IDs either with or without dashes in most places; this
    normalizes them so internal comparisons and log messages are consistent.
    """
    return customer_id.replace("-", "").strip()


def is_valid_customer_id(customer_id: str) -> bool:
    """True if customer_id looks like a Google Ads customer ID (digits and
    optional dashes, at least one digit)."""
    return bool(re.fullmatch(r"[\d\-]+", customer_id or "")) and bool(
        re.search(r"\d", customer_id or "")
    )
