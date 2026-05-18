"""
Parser for electronics ads (recommerce category).

Converts raw `docs[i]` objects from api.search() into dictionaries
that map directly to the Listing model. The conversion is pure —
no database access — so we can unit test it against saved JSON
samples without setting up Postgres.
"""

from typing import Any

from src.services.parsing.common import (
    derive_seller_type,
    parse_blocket_flags,
    parse_blocket_timestamp,
    parse_coordinates,
    parse_price,
)


# Fields that go directly into the Listing model. Returned as a
# plain dict so the sync service can construct the SQLAlchemy
# object — keeping parsing pure makes testing easier.
def parse_electronics_listing(doc: dict[str, Any]) -> dict[str, Any]:
    """Convert a single electronics ad from Blocket into Listing kwargs.

    Args:
        doc: One item from the 'docs' array of api.search() response.

    Returns:
        Dict ready to pass as **kwargs to Listing(...).
        Always includes a 'blocket_id' key — that's the primary
        identity we use for deduplication.
    """
    # ── Identity ─────────────────────────────────────────────────
    # 'ad_id' is an int; we store it as string for consistency with
    # the Listing.blocket_id column (which is String, not Integer)
    blocket_id = str(doc.get("ad_id") or doc.get("id"))

    # ── Flags and seller ────────────────────────────────────────
    flags = doc.get("flags", []) or []
    organisation_name = doc.get("organisation_name")
    seller_type = derive_seller_type(flags, organisation_name)
    flag_bools = parse_blocket_flags(flags)

    # ── Coordinates ─────────────────────────────────────────────
    latitude, longitude = parse_coordinates(doc.get("coordinates"))

    # ── Images ──────────────────────────────────────────────────
    image_urls = doc.get("image_urls", []) or []
    # The primary image is in a separate 'image.url' field, but it
    # usually matches the first entry of image_urls anyway
    primary_image = None
    if isinstance(doc.get("image"), dict):
        primary_image = doc["image"].get("url")
    if not primary_image and image_urls:
        primary_image = image_urls[0]

    return {
        # Identity
        "blocket_id": blocket_id,
        "category": "electronics",
        # Content
        "heading": doc.get("heading", "") or "",
        # Description isn't in the search response — populated later
        # by a separate fetch via api.get_ad()
        "description": None,
        "description_fetched_at": None,
        # Price
        "price": parse_price(doc.get("price")),
        # Location
        "location": doc.get("location"),
        "latitude": latitude,
        "longitude": longitude,
        # Seller
        "seller_type": seller_type,
        "organisation_name": organisation_name,
        # Media
        "image_urls": image_urls,
        "primary_image_url": primary_image,
        # Flags
        "blocket_flags_raw": flags,
        "can_be_shipped": flag_bools["can_be_shipped"],
        "buy_now_available": flag_bools["buy_now_available"],
        "seller_pays_shipping": flag_bools["seller_pays_shipping"],
        # Links
        "canonical_url": doc.get("canonical_url"),
        # Timestamps
        "posted_at": parse_blocket_timestamp(doc.get("timestamp")),
    }
