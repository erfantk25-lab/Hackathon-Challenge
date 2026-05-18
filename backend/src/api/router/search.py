from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.db.core import get_db
from src.db.models import CredibilityScore, Listing, ListingEmbedding
from src.services.embedding_service import embed_text


router = APIRouter(prefix="/api", tags=["Search"])


CATEGORY_ALIASES = {
    "electronics": "electronics",
    "elektronik": "electronics",
    "cars": "cars",
    "fordon": "cars",
    "bilar": "cars",
}


def _normalize_category(category: str | None) -> str | None:
    if category is None:
        return None

    normalized = CATEGORY_ALIASES.get(category.strip().lower())
    if not normalized:
        raise HTTPException(
            status_code=422,
            detail="category must be electronics, cars, elektronik, fordon, or bilar",
        )
    return normalized


def _listing_to_dict(
    listing: Listing,
    score: CredibilityScore | None = None,
    distance: float | None = None,
) -> dict:
    reasons = score.reasons if score else []
    return {
        "id": listing.id,
        "blocket_id": listing.blocket_id,
        "category": listing.category,
        "heading": listing.heading,
        "description": listing.description,
        "price": float(listing.price) if listing.price is not None else None,
        "location": listing.location,
        "seller_type": listing.seller_type,
        "image_urls": listing.image_urls or [],
        "primary_image_url": listing.primary_image_url,
        "canonical_url": listing.canonical_url,
        "posted_at": listing.posted_at,
        "first_seen_at": listing.first_seen_at,
        "credibility_score": float(score.credibility_score) if score else None,
        "scam_probability": (
            float(score.scam_probability)
            if score and score.scam_probability is not None
            else None
        ),
        "flags": [
            reason.get("code")
            for reason in reasons
            if isinstance(reason, dict) and reason.get("code")
        ],
        "semantic_distance": distance,
    }


def _latest_scores(db: Session, listing_ids: list[int]) -> dict[int, CredibilityScore]:
    """Return the most recent score per listing_id.

    Uses PostgreSQL's DISTINCT ON to get exactly one row per
    listing — the one with the highest scored_at.
    """
    if not listing_ids:
        return {}

    from sqlalchemy import text

    rows = db.execute(
        text("""
        SELECT DISTINCT ON (listing_id) *
        FROM credibility_scores
        WHERE listing_id = ANY(:ids)
        ORDER BY listing_id, scored_at DESC
    """),
        {"ids": listing_ids},
    ).fetchall()

    return {row.listing_id: row for row in rows}


def _base_filters(
    query,
    category: str | None,
    location: str | None,
    min_price: Decimal | None,
    max_price: Decimal | None,
):
    if category:
        query = query.filter(Listing.category == category)
    if location:
        query = query.filter(Listing.location.ilike(f"%{location}%"))
    if min_price is not None:
        query = query.filter(Listing.price >= min_price)
    if max_price is not None:
        query = query.filter(Listing.price <= max_price)
    return query


@router.get("/search")
async def search_listings(
    q: str = "",
    query: str | None = None,
    category: str | None = None,
    location: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = (q or query or "").strip()
    category = _normalize_category(category)

    base = db.query(Listing)
    base = _base_filters(base, category, location, min_price, max_price)

    if q.strip():
        vector_count = db.query(ListingEmbedding).count()
        if vector_count:
            try:
                query_vector = embed_text(q)
            except Exception as exc:
                raise HTTPException(
                    status_code=500, detail=f"Embedding failed: {exc}"
                ) from exc

            distance = ListingEmbedding.embedding.cosine_distance(query_vector).label(
                "semantic_distance"
            )
            rows = (
                db.query(Listing, distance)
                .join(ListingEmbedding, ListingEmbedding.listing_id == Listing.id)
                .filter(Listing.id.in_(base.with_entities(Listing.id)))
                .order_by(distance)
                .offset(offset)
                .limit(limit)
                .all()
            )
            listings = [row[0] for row in rows]
            distances = {row[0].id: float(row[1]) for row in rows}
        else:
            rows = (
                base.filter(
                    or_(
                        Listing.heading.ilike(f"%{q}%"),
                        Listing.description.ilike(f"%{q}%"),
                    )
                )
                .order_by(Listing.posted_at.desc().nullslast(), Listing.id.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            listings = rows
            distances = {}
    else:
        listings = (
            base.order_by(Listing.posted_at.desc().nullslast(), Listing.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        distances = {}

    scores = _latest_scores(db, [listing.id for listing in listings])
    total = base.count()
    trusted_count = sum(
        1
        for score in scores.values()
        if score.credibility_score is not None and float(score.credibility_score) >= 7
    )
    suspicious_count = sum(
        1
        for score in scores.values()
        if score.credibility_score is not None and float(score.credibility_score) < 4
    )

    return {
        "query": q or None,
        "total": total,
        "trusted_count": trusted_count,
        "suspicious_count": suspicious_count,
        "results": [
            _listing_to_dict(listing, scores.get(listing.id), distances.get(listing.id))
            for listing in listings
        ],
    }


@router.get("/similar/{listing_id}")
async def similar_listings(
    listing_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    source = db.get(ListingEmbedding, listing_id)
    if not source:
        raise HTTPException(status_code=404, detail="Listing has no embedding yet")

    distance = ListingEmbedding.embedding.cosine_distance(source.embedding).label(
        "semantic_distance"
    )
    rows = (
        db.query(Listing, distance)
        .join(ListingEmbedding, ListingEmbedding.listing_id == Listing.id)
        .filter(Listing.id != listing_id)
        .order_by(distance)
        .limit(limit)
        .all()
    )

    listings = [row[0] for row in rows]
    scores = _latest_scores(db, [listing.id for listing in listings])
    return {
        "listing_id": listing_id,
        "results": [
            _listing_to_dict(listing, scores.get(listing.id), float(distance_value))
            for listing, distance_value in rows
        ],
    }
