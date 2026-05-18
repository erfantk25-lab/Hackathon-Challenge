from pydantic import BaseModel
from schemas.ad import ListingWithScore

class SearchQuery(BaseModel):
    query: str
    category: str
    location: str | None = None
    min_price: int | None = None
    max_price: int | None = None

class SearchResult(BaseModel):
    query: str
    total: int
    results: list[ListingWithScore]