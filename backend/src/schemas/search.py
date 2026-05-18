"""
Pydantic schemas for search requests and responses.
"""
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

from src.schemas.ad import ListingWithScore


class SearchQuery(BaseModel):
    """A search query coming from the frontend.

    Categories is a list because the spec requires at least 2 to be
    selectable. Free-text query is optional — empty query plus
    filters = "browse this category".
    """
    query: Optional[str] = None
    categories: list[Literal["electronics", "cars"]] = Field(default_factory=list)
    location: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    min_credibility: Optional[Decimal] = Field(None, ge=1, le=10)
    limit: int = Field(20, ge=1, le=100)
    offset: int = 0


class SearchResult(BaseModel):
    """A page of search results plus aggregate stats for the UI."""
    query: Optional[str] = None
    total: int
    results: list[ListingWithScore]
    
    # Aggregate stats used by the frontend's summary cards
    median_price: Optional[Decimal] = None
    trusted_count: int = 0           # credibility >= 7
    suspicious_count: int = 0        # credibility < 4
    
    # AI summary when natural-language search was used
    ai_summary: Optional[str] = None