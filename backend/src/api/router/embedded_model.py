import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAIError
from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.config import settings
from src.db.core import get_db
from src.db.models import LLMAnalysis, Listing, ListingEmbedding
from src.schemas.analysis import AnalysisRequest, LLMAnalysis as LLMAnalysisSchema, VectorizeResult
from src.services.embedding_service import embed_batch, embed_text, get_ai_client, listing_text


router = APIRouter(prefix="/api/ai", tags=["AI"])


def _json_from_text(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").replace("json\n", "", 1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start : end + 1]
    return json.loads(text)


def _analysis_response(row: LLMAnalysis, cached: bool) -> LLMAnalysisSchema:
    data = row.response
    return LLMAnalysisSchema(
        listing_id=row.listing_id,
        summary=data.get("summary", ""),
        price_verdict=data.get("price_verdict", "okänt"),
        risk_level=data.get("risk_level", "medel"),
        red_flags=data.get("red_flags", []),
        green_flags=data.get("green_flags", []),
        cached=cached,
        analyzed_at=row.analyzed_at,
    )


def _ai_error(message: str, exc: Exception) -> HTTPException:
    return HTTPException(status_code=502, detail=f"{message}: {exc}")


async def _embed_listings(db: Session, listings: list[Listing]) -> tuple[int, list[int], int | None]:
    if not listings:
        return 0, [], None

    try:
        vectors = await embed_batch([listing_text(listing) for listing in listings])
    except (OpenAIError, ValueError) as exc:
        raise _ai_error("Embedding request failed", exc) from exc

    for listing, vector in zip(listings, vectors):
        db.merge(
            ListingEmbedding(
                listing_id=listing.id,
                embedding=vector,
                model_name=settings.EMBEDDING_MODEL,
                embedded_at=datetime.utcnow(),
            )
        )
    db.commit()
    dimensions = len(vectors[0]) if vectors else None
    return len(vectors), [listing.id for listing in listings], dimensions


@router.get("/health")
async def ai_health():
    try:
        models = await get_ai_client().models.list()
    except OpenAIError as exc:
        raise _ai_error("AI server is not reachable", exc) from exc

    model_ids = [model.id for model in models.data]
    return {
        "base_url": settings.ai_base_url,
        "chat_model": settings.OPENAI_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
        "models": model_ids,
    }


@router.get("/embedding-test")
async def embedding_test(text: str = "test"):
    try:
        vector = await embed_text(text)
    except (OpenAIError, ValueError) as exc:
        raise _ai_error("Embedding test failed", exc) from exc

    return {
        "model": settings.EMBEDDING_MODEL,
        "dimensions": len(vector),
        "sample": vector[:5],
    }


@router.post("/analyze", response_model=LLMAnalysisSchema)
async def analyze_listing(request: AnalysisRequest, db: Session = Depends(get_db)):
    listing = db.get(Listing, request.listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    cached = (
        db.query(LLMAnalysis)
        .filter(
            LLMAnalysis.listing_id == listing.id,
            LLMAnalysis.analysis_type == "scam_analysis",
            LLMAnalysis.prompt_version == "v1",
        )
        .order_by(desc(LLMAnalysis.analyzed_at))
        .first()
    )
    if cached:
        return _analysis_response(cached, cached=True)

    prompt = {
        "id": listing.id,
        "category": listing.category,
        "heading": listing.heading,
        "description": listing.description,
        "price": str(listing.price) if listing.price is not None else None,
        "location": listing.location,
        "seller_type": listing.seller_type,
    }

    try:
        response = await get_ai_client().chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Analyze Swedish classified ads for scam risk. "
                        "Return only JSON with keys summary, price_verdict, "
                        "risk_level, red_flags, green_flags. "
                        "price_verdict must be rimligt, lågt, högt, or okänt. "
                        "risk_level must be låg, medel, or hög."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            temperature=0.2,
        )
    except OpenAIError as exc:
        raise _ai_error("AI analysis request failed", exc) from exc

    raw = response.choices[0].message.content or "{}"
    try:
        parsed = _json_from_text(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"AI returned invalid JSON: {raw}") from exc

    row = LLMAnalysis(
        listing_id=listing.id,
        analysis_type="scam_analysis",
        prompt_version="v1",
        response=parsed,
        input_tokens=getattr(response.usage, "prompt_tokens", None),
        output_tokens=getattr(response.usage, "completion_tokens", None),
        model_name=settings.OPENAI_MODEL,
        analyzed_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _analysis_response(row, cached=False)


@router.post("/vectorize/missing", response_model=VectorizeResult)
async def vectorize_missing(limit: int = 100, db: Session = Depends(get_db)):
    listings = (
        db.query(Listing)
        .outerjoin(ListingEmbedding, ListingEmbedding.listing_id == Listing.id)
        .filter(ListingEmbedding.listing_id.is_(None))
        .order_by(Listing.id.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    embedded, listing_ids, dimensions = await _embed_listings(db, listings)
    return VectorizeResult(
        embedded=embedded,
        model=settings.EMBEDDING_MODEL,
        dimensions=dimensions,
        listing_ids=listing_ids,
    )


@router.post("/vectorize/{listing_id}", response_model=VectorizeResult)
async def vectorize_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    embedded, listing_ids, dimensions = await _embed_listings(db, [listing])
    return VectorizeResult(
        embedded=embedded,
        model=settings.EMBEDDING_MODEL,
        dimensions=dimensions,
        listing_ids=listing_ids,
    )
