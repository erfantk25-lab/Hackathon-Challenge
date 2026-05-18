"""
Pydantic schemas for ads.

Field names mirror the Blocket API where possible (e.g. 'heading'
instead of 'subject') so the mapping from API → schema is obvious.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


# ────────────────────────────────────────────────────────────────
# Building blocks
# ────────────────────────────────────────────────────────────────
class Coordinates(BaseModel):
    """Geographic coordinates from Blocket's 'coordinates' field."""

    latitude: float
    longitude: float


class BlocketFlags(BaseModel):
    """Boolean flags derived from Blocket's 'flags' array.

    Cleaner to expose as named booleans than as a raw list of strings.
    """

    is_private: bool = False
    is_retailer: bool = False
    can_be_shipped: bool = False
    buy_now_available: bool = False
    seller_pays_shipping: bool = False


# ────────────────────────────────────────────────────────────────
# Cars: structured fields unique to vehicles
# ────────────────────────────────────────────────────────────────
class CarDetails(BaseModel):
    """Car-specific fields from api.search_car()."""

    make: Optional[str] = None  # 'Volvo'
    model: Optional[str] = None  # 'XC60'
    model_specification: Optional[str] = None  # seller's equipment description
    year: Optional[int] = None
    mileage: Optional[int] = None  # in Scandinavian miles (1 mil = 10 km)
    fuel: Optional[str] = None  # 'Diesel', 'Bensin', 'El', etc.
    transmission: Optional[str] = None  # 'Automatisk', 'Manuell'
    regno: Optional[str] = None  # registration number
    chassis_number: Optional[str] = None
    dealer_segment: Optional[str] = None  # 'Företag', 'Privat'


# ────────────────────────────────────────────────────────────────
# Listing: the main schema
# ────────────────────────────────────────────────────────────────
class ListingBase(BaseModel):
    """Fields shared by all listing schemas."""

    blocket_id: str
    category: Literal["electronics", "cars"]
    heading: str
    description: Optional[str] = None
    price: Optional[Decimal] = None
    location: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    seller_type: Optional[Literal["private", "company"]] = None
    organisation_name: Optional[str] = None
    image_urls: list[str] = []
    primary_image_url: Optional[str] = None
    blocket_flags: BlocketFlags = BlocketFlags()
    canonical_url: Optional[str] = None
    posted_at: Optional[datetime] = None


class ListingCreate(ListingBase):
    """Schema for creating a listing from a sync worker."""

    car_details: Optional[CarDetails] = None


class Listing(ListingBase):
    """Schema returned from the API to the frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: int  # our internal DB id
    first_seen_at: datetime
    car_details: Optional[CarDetails] = None
    is_active: bool = True


class ListingWithScore(Listing):
    """Listing enriched with its latest credibility score.

    Used by search results — embedding score saves a separate request.
    """

    credibility_score: Optional[Decimal] = None
    scam_probability: Optional[Decimal] = None
    flags: list[str] = []
