from fastapi import APIRouter
from unittest.mock import MagicMock
from src.scoring.engine import score_ad
from blocket_api import BlocketAPI, Category, Location

router = APIRouter()
api = BlocketAPI()

CATEGORY_MAP = {
    "elektronik": Category.ELEKTRONIK,
    "fordon": Category.FORDON,
}

LOCATION_MAP = {
    "stockholm": Location.STOCKHOLM,
    "goteborg": Location.GOTEBORG,
    "malmo": Location.MALMO,
}


def format_ad(ad, score_output) -> dict:
    return {
        "id": ad.id,
        "subject": ad.subject,
        "price": ad.price,
        "location": ad.location,
        "url": ad.url,
        "image_count": len(ad.images or []),
        "score": score_output.score,
        "is_suspicious": score_output.is_suspicious,
        "rule_score": score_output.rule_score,
        "reasons": score_output.reasons
    }


@router.get("/test-score")
def test_score():
    """Test endpoint with fake data — use in Swagger to verify scoring works."""
    fake_ad = MagicMock()
    fake_ad.images = ["img1.jpg", "img2.jpg", "img3.jpg"]
    fake_ad.body = "Säljer en iPhone 14 Pro i mycket bra skick. Köpt för ett år sedan, inga repor."
    fake_ad.location = "Stockholm"
    fake_ad.price = 7500
    fake_ad.category = "elektronik"
    fake_ad.store = None

    result = score_ad(fake_ad)
    return format_ad(fake_ad, result)


@router.get("/search")
def search_ads(query: str, category: str = "elektronik", location: str = "stockholm"):
    """Search Blocket and return scored ads."""
    blocket_category = CATEGORY_MAP.get(category.lower())
    blocket_location = LOCATION_MAP.get(location.lower())

    results = api.search(
        query,
        category=blocket_category,
        locations=[blocket_location] if blocket_location else None
    )

    scored = []
    for ad in results:
        score_output = score_ad(ad)
        scored.append(format_ad(ad, score_output))

    # Sort — suspicious ads to the bottom, best scores to the top
    scored.sort(key=lambda x: x["score"], reverse=True)

    suspicious = [a for a in scored if a["is_suspicious"]]

    return {
        "total": len(scored),
        "suspicious_count": len(suspicious),
        "results": scored,
        "suspicious": suspicious
    }