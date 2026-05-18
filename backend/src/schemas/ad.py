from pydantic import BaseModel
from datetime import datetime

class Listing(BaseModel):
    id: str
    subject: str
    body: str | None
    price: int | None
    location: str | None
    url: str
    image_count: int
    seller_type: str | None
    category: str
    first_seen: datetime

class ScoreReason(BaseModel):
    reason: str
    flag_type: str    # 'Grön', 'Gul', 'Röd'
    source: str       

class Score(BaseModel):
    ad_id: str
    score: int        # 0-10
    is_suspicious: bool
    reasons: list[ScoreReason]

class SearchQuery(BaseModel):
    query: str
    category: str
    location: str | None
    min_price: int | None
    max_price: int | None