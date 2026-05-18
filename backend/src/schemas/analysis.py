"""
Pydantic schemas for credibility analysis and LLM responses.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ScoreReason(BaseModel):
    """One reason behind a credibility score.

    Flag type uses a traffic-light system that maps directly to UI
    badge colors: green = positive, yellow = caution, red = warning.
    """
    code: str                                       # e.g. 'price_far_below_median'
    message: str                                    # Swedish, shown in UI
    flag_type: Literal["green", "yellow", "red"]
    source: Literal["rules", "llm", "ml_model"]    # which subsystem flagged it


class CredibilityScore(BaseModel):
    """A scoring run for a listing."""
    model_config = ConfigDict(from_attributes=True)
    
    listing_id: int
    credibility_score: Decimal = Field(..., ge=1, le=10)
    scam_probability: Optional[Decimal] = None
    reasons: list[ScoreReason] = []
    model_version: str
    scored_at: datetime


class AnalysisRequest(BaseModel):
    """Request body for the LLM analysis endpoint."""
    listing_id: int


class LLMAnalysis(BaseModel):
    """Claude's structured analysis of a listing."""
    model_config = ConfigDict(from_attributes=True)
    
    listing_id: int
    summary: str                                       # short Swedish text
    price_verdict: Literal["rimligt", "lågt", "högt", "okänt"]
    risk_level: Literal["låg", "medel", "hög"]
    red_flags: list[str] = []
    green_flags: list[str] = []
    cached: bool = False                               # whether served from cache
    analyzed_at: datetime


class VectorizeResult(BaseModel):
    embedded: int
    model: str
    dimensions: Optional[int] = None
    listing_ids: list[int] = []
