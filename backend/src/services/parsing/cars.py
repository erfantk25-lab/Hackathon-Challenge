"""
Parser for car ads from api.search_car().

Returns TWO dicts:
  - listing_dict: common fields → Listing model
  - car_details_dict: car-specific fields → CarDetails model

Cars use a dedicated Blocket endpoint with more structured data
than recommerce search. Most fields are at the top level rather
than nested in 'extras'.
"""
from typing import Any, Optional

from src.services.parsing.common import (
    derive_seller_type,
    parse_blocket_flags,
    parse_blocket_timestamp,
    parse_coordinates,
    parse_price,
)


def parse_car_listing(doc: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert a single car ad into (Listing kwargs, CarDetails kwargs).

    The two returned dicts are meant to be used like:
        listing = Listing(**listing_dict)
        car = CarDetails(listing_id=listing.id, **car_details_dict)

    Args:
        doc: One item from the 'docs' array of api.search_car() response.

    Returns:
        Tuple of (listing_kwargs, car_details_kwargs).
    """
    # ── Identity ─────────────────────────────────────────────────
    blocket_id = str(doc.get("ad_id") or doc.get("id"))

    # ── Seller type for cars ────────────────────────────────────
    # Cars often have 'dealer_segment' set to 'Företag' / 'Privat'
    # which is a more direct signal than the flags array
    flags = doc.get("flags", []) or []
    organisation_name = doc.get("organisation_name")
    dealer_segment = doc.get("dealer_segment")

    if dealer_segment == "Privat":
        seller_type = "private"
    elif dealer_segment == "Företag" or organisation_name:
        seller_type = "company"
    else:
        # Fall back to flag-based detection
        seller_type = derive_seller_type(flags, organisation_name)

    flag_bools = parse_blocket_flags(flags)

    # ── Coordinates ─────────────────────────────────────────────
    latitude, longitude = parse_coordinates(doc.get("coordinates"))

    # ── Images ──────────────────────────────────────────────────
    image_urls = doc.get("image_urls", []) or []
    primary_image = None
    if isinstance(doc.get("image"), dict):
        primary_image = doc["image"].get("url")
    if not primary_image and image_urls:
        primary_image = image_urls[0]

    # Build the heading: cars sometimes have a separate 'facade_title'
    # that's nicer than 'heading' (which can be the same value).
    # We use whichever is set.
    heading = doc.get("heading") or doc.get("facade_title") or ""

    # ── Listing dict ────────────────────────────────────────────
    listing_dict = {
        "blocket_id": blocket_id,
        "category": "cars",

        "heading": heading,
        "description": None,
        "description_fetched_at": None,

        "price": parse_price(doc.get("price")),

        "location": doc.get("location"),
        "latitude": latitude,
        "longitude": longitude,

        "seller_type": seller_type,
        "organisation_name": organisation_name,

        "image_urls": image_urls,
        "primary_image_url": primary_image,

        "blocket_flags_raw": flags,
        "can_be_shipped": flag_bools["can_be_shipped"],
        "buy_now_available": flag_bools["buy_now_available"],
        "seller_pays_shipping": flag_bools["seller_pays_shipping"],

        "canonical_url": doc.get("canonical_url"),
        "posted_at": parse_blocket_timestamp(doc.get("timestamp")),
    }

    # ── CarDetails dict ─────────────────────────────────────────
    # Mileage is stored as an integer in Scandinavian miles
    # (1 mil = 10 km). Year is a 4-digit integer.
    car_details_dict = {
        "make": doc.get("make"),
        "model": doc.get("model"),
        "model_specification": doc.get("model_specification"),
        "year": _safe_int(doc.get("year")),
        "mileage": _safe_int(doc.get("mileage")),
        "fuel": doc.get("fuel"),
        "transmission": doc.get("transmission"),
        "regno": doc.get("regno"),
        "chassis_number": doc.get("chassis_number"),
        "dealer_segment": dealer_segment,
        "dealer_group_id": doc.get("dealer_group_id"),
    }

    return listing_dict, car_details_dict


def _safe_int(value: Any) -> Optional[int]:
    """Convert a value to int, returning None on failure.
    
    Useful for fields like 'year' and 'mileage' that should be
    integers but might be missing or malformed.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None