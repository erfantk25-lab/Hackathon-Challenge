"""
AI analysis endpoints.

Provides LLM-based scam analysis using OpenAI GPT-4o-mini. Each
analysis is cached in the llm_analyses table so we don't pay for
the same query twice.

Embeddings are handled separately by the sync service using local
sentence-transformers (see services/embedding_service.py).
"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAIError, AsyncOpenAI
from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.config import settings
from src.db.core import get_db
from src.db.models import Listing, LLMAnalysis
from src.schemas.analysis import (
    AnalysisRequest,
    LLMAnalysis as LLMAnalysisSchema,
)


router = APIRouter(prefix="/api/ai", tags=["AI"])


def _get_ai_client() -> AsyncOpenAI:
    """Build an OpenAI client from settings.

    Kept local to this module since only LLM analysis uses OpenAI.
    Embeddings use a separate local pipeline.
    """
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _json_from_text(text: str) -> dict:
    """Extract a JSON object from a model response.
    
    Models sometimes wrap JSON in markdown fences or add prose
    around it; this strips that and parses the result.
    """
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


@router.get("/health")
async def ai_health():
    """Verify that the OpenAI API is reachable from this backend."""
    try:
        models = await _get_ai_client().models.list()
    except OpenAIError as exc:
        raise _ai_error("AI server is not reachable", exc) from exc

    return {
        "chat_model": settings.OPENAI_MODEL,
        "available_models": [m.id for m in models.data][:10],
    }


@router.post("/analyze", response_model=LLMAnalysisSchema)
async def analyze_listing(
    request: AnalysisRequest,
    db: Session = Depends(get_db),
):
    """Run LLM-based scam analysis for a single listing.
    
    Cached: if we've already analysed this listing with this prompt
    version, return the cached result rather than calling OpenAI again.
    """
    listing = db.get(Listing, request.listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Cache lookup
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

    # Build the prompt payload
    prompt = {
        "id": listing.id,
        "category": listing.category,
        "heading": listing.heading,
        "description": listing.description,
        "price": str(listing.price) if listing.price is not None else None,
        "location": listing.location,
        "seller_type": listing.seller_type,
    }

    # Call the model
    try:
        response = await _get_ai_client().chat.completions.create(
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
                {
                    "role": "user",
                    "content": json.dumps(prompt, ensure_ascii=False),
                },
            ],
            temperature=0.2,
        )
    except OpenAIError as exc:
        raise _ai_error("AI analysis request failed", exc) from exc

    # Parse and persist
    raw = response.choices[0].message.content or "{}"
    try:
        parsed = _json_from_text(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI returned invalid JSON: {raw}",
        ) from exc

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