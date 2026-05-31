"""
utils.py — Shared utility functions used by seed.py and admin_routes.py
"""
import re
import json
import math
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def slugify(text: str) -> str:
    """'Lahore Fort' → 'lahore-fort'"""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def safe_str(value, fallback: str = "") -> str:
    """Convert value to string, treating None/NaN as fallback."""
    if value is None:
        return fallback
    try:
        if isinstance(value, float) and math.isnan(value):
            return fallback
    except (TypeError, ValueError):
        pass
    result = str(value).strip()
    return result if result else fallback


def safe_float(value, fallback=None):
    """Convert to float, returning fallback on NaN/None/error."""
    if value is None:
        return fallback
    try:
        if isinstance(value, float) and math.isnan(value):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def safe_json(value, fallback: str = "[]") -> str:
    """
    Ensure value is stored as a valid JSON array string.
    Handles: '["mughal","fort"]', 'mughal, fort', None, NaN.
    """
    if value is None:
        return fallback
    try:
        if isinstance(value, float) and math.isnan(value):
            return fallback
    except (TypeError, ValueError):
        pass

    val_str = str(value).strip()
    if not val_str:
        return fallback

    # Already valid JSON array
    if val_str.startswith("["):
        try:
            json.loads(val_str)
            return val_str
        except json.JSONDecodeError:
            pass

    # Comma-separated plain text → convert to JSON array
    tags = [t.strip() for t in val_str.split(",") if t.strip()]
    return json.dumps(tags)