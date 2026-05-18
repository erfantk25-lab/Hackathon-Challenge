"""
Shared parsing helpers used across categories.

These functions convert raw fields from Blocket's API into the
shapes our database expects. Keeping them in one place ensures
that 'private' means the same thing for an iPhone listing as
for a car listing.
"""

from datetime import datetime, timezone
from typing import Any, Optional


# ── Timestamps ──────────────────────────────────────────────────
def parse_blocket_timestamp(value: Any) -> Optional[datetime]:
    """Convert Blocket's millisecond unix timestamp to a datetime.

    Blocket returns timestamps as integers like 1779093442000.
    Returns None if the value is missing or unparseable.

    Args:
        value: Raw timestamp from the API.

    Returns:
        A naive UTC datetime suitable for storing in SQLAlchemy.
    """
    if not value:
        return None
    try:
        # Divide by 1000 because Blocket uses milliseconds, not seconds
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).replace(
            tzinfo=None
        )
    except (TypeError, ValueError):
        return None


# ── Seller type ─────────────────────────────────────────────────
def derive_seller_type(flags: list[str], organisation_name: Optional[str]) -> str:
    """Determine whether a listing is from a private seller or company.

    Blocket signals this in two places:
      - 'flags' contains either 'private' or 'retailer'
      - 'organisation_name' is set only for companies

    We default to 'private' if neither signal is present, since
    that's the more common case on Blocket.

    Args:
        flags: Raw flags list from the API.
        organisation_name: Organisation name (None for private).

    Returns:
        Either 'private' or 'company'.
    """
    if "retailer" in flags or organisation_name:
        return "company"
    return "private"


# ── Blocket flags → booleans ────────────────────────────────────
def parse_blocket_flags(flags: list[str]) -> dict[str, bool]:
    """Convert Blocket's flag array into named booleans.

    The raw flags list contains strings like 'shipping_exists' or
    'buy_now'. Booleans are easier to query against than 'flag X in
    array Y' SQL.

    Args:
        flags: Raw flags list from the API.

    Returns:
        Dict with shipping/buy_now/seller_pays_shipping booleans.
    """
    return {
        "can_be_shipped": "shipping_exists" in flags,
        "buy_now_available": "buy_now" in flags,
        "seller_pays_shipping": "seller_pays_shipping" in flags,
    }


# ── Price extraction ────────────────────────────────────────────
def parse_price(price_field: Any) -> Optional[float]:
    """Extract numeric price from Blocket's price object or int.

    Blocket sometimes returns price as an object:
        {"amount": 7900, "currency_code": "SEK", "price_unit": "kr"}
    And sometimes as a plain integer (in detail responses).

    Args:
        price_field: The raw 'price' value from the API.

    Returns:
        Price as float, or None if missing or unparseable.
    """
    if price_field is None:
        return None
    if isinstance(price_field, (int, float)):
        return float(price_field)
    if isinstance(price_field, dict):
        amount = price_field.get("amount")
        if amount is not None:
            try:
                return float(amount)
            except (TypeError, ValueError):
                return None
    return None


# ── Coordinates ─────────────────────────────────────────────────
def parse_coordinates(coords: Any) -> tuple[Optional[float], Optional[float]]:
    """Extract (latitude, longitude) from Blocket's coordinates dict.

    Blocket returns:
        {"lat": 59.33081, "lon": 18.05457, "accuracy": 5}

    Returns:
        Tuple (lat, lon) or (None, None) if the data is missing.
    """
    if not isinstance(coords, dict):
        return None, None
    lat = coords.get("lat")
    lon = coords.get("lon")
    if lat is None or lon is None:
        return None, None
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None, None
