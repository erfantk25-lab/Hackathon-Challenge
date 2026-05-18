"""
SQLAlchemy models for Blocket Smart Search.

Schema is designed against actual responses from blocket_api:
- api.search()      → recommerce ads (electronics, etc)
- api.search_car()  → car ads (15+ extra structured fields)
- api.get_ad()      → detail view including description

Design philosophy:
- One core table (listings) for fields all categories share
- One sidecar table per category for category-specific fields
- Volatile state (last_seen, scores) split into separate tables
  so they can be updated without touching canonical ad data
"""
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ════════════════════════════════════════════════════════════════
# Core listing
# ════════════════════════════════════════════════════════════════
class Listing(Base):
    """A single Blocket ad — fields common to all categories.

    Only fields that both electronics and cars carry live here.
    Category-specific structured fields go in sidecar tables.

    The `description` column is filled in lazily via api.get_ad()
    after the initial search response is stored, so it can be
    NULL even for active listings.
    """

    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ── Blocket identity ─────────────────────────────────────────
    # Stored as string even though Blocket uses an integer ad_id,
    # to leave room for future categories that might use other IDs.
    blocket_id = Column(String, unique=True, nullable=False, index=True)

    # 'electronics' | 'cars' (extend Literal in schemas when adding more)
    category = Column(String, nullable=False, index=True)

    # ── Content ──────────────────────────────────────────────────
    heading = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    description_fetched_at = Column(DateTime, nullable=True)

    # Price extracted from price.amount (currency is always SEK)
    price = Column(Numeric(12, 2), nullable=True)

    # ── Location ─────────────────────────────────────────────────
    location = Column(String, nullable=True)
    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)

    # ── Seller ───────────────────────────────────────────────────
    # Derived from Blocket's flags array ('private' / 'retailer')
    seller_type = Column(String, nullable=True)
    # Only set when seller_type == 'company'
    organisation_name = Column(String, nullable=True)

    # ── Media ────────────────────────────────────────────────────
    image_urls = Column(JSON, nullable=False, default=list)
    primary_image_url = Column(String, nullable=True)

    # ── Blocket flags ────────────────────────────────────────────
    # Raw flags array kept as JSON so we don't lose any info that
    # Blocket adds later. Booleans below are the ones we actually
    # use in scoring; they're derived from this array at parse time.
    blocket_flags_raw = Column(JSON, nullable=False, default=list)
    can_be_shipped = Column(Boolean, default=False, nullable=False)
    buy_now_available = Column(Boolean, default=False, nullable=False)
    seller_pays_shipping = Column(Boolean, default=False, nullable=False)

    # ── Canonical URL on Blocket ─────────────────────────────────
    canonical_url = Column(String, nullable=True)

    # ── Timestamps ───────────────────────────────────────────────
    # When the ad was posted on Blocket (from their 'timestamp' field
    # which is unix milliseconds — divide by 1000 when parsing)
    posted_at = Column(DateTime, nullable=True)

    # When we first observed this ad
    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Last time we mutated this row
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────
    activity = relationship(
        "ListingActivity",
        back_populates="listing",
        uselist=False,
        cascade="all, delete-orphan",
    )
    car_details = relationship(
        "CarDetails",
        back_populates="listing",
        uselist=False,
        cascade="all, delete-orphan",
    )
    price_history = relationship(
        "PriceHistory",
        back_populates="listing",
        cascade="all, delete-orphan",
    )
    features = relationship(
        "ListingFeatures",
        back_populates="listing",
        uselist=False,
        cascade="all, delete-orphan",
    )
    scores = relationship(
        "CredibilityScore",
        back_populates="listing",
        cascade="all, delete-orphan",
    )
    llm_analyses = relationship(
        "LLMAnalysis",
        back_populates="listing",
        cascade="all, delete-orphan",
    )
    embedding = relationship(
        "ListingEmbedding",
        back_populates="listing",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_listings_category_price", "category", "price"),
        Index("idx_listings_posted_at", "posted_at"),
        Index("idx_listings_seller_type", "seller_type"),
    )


# ════════════════════════════════════════════════════════════════
# Car-specific sidecar
# ════════════════════════════════════════════════════════════════
class CarDetails(Base):
    """Car-specific structured fields from api.search_car().

    1:1 with Listing when listing.category == 'cars'. Lifted into
    its own table because 15+ car-only fields would be NULL on
    every electronics row — wasteful and noisy.
    """

    __tablename__ = "car_details"

    listing_id = Column(
        Integer,
        ForeignKey("listings.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # ── Brand and model ──────────────────────────────────────────
    make = Column(String, nullable=True, index=True)            # 'Volvo'
    model = Column(String, nullable=True, index=True)           # 'XC60'
    # Seller-written equipment description, free text
    model_specification = Column(Text, nullable=True)

    # ── Numeric specs ────────────────────────────────────────────
    year = Column(Integer, nullable=True, index=True)
    # In Scandinavian miles (1 mil = 10 km). Multiply by 10 for km.
    mileage = Column(Integer, nullable=True, index=True)

    # ── Categorical specs ────────────────────────────────────────
    fuel = Column(String, nullable=True)            # 'Diesel', 'Bensin', 'El', 'Hybrid'
    transmission = Column(String, nullable=True)    # 'Automatisk', 'Manuell'

    # ── Identifiers (useful for fraud detection) ─────────────────
    regno = Column(String, nullable=True, index=True)
    chassis_number = Column(String, nullable=True, index=True)

    # ── Dealer info ──────────────────────────────────────────────
    dealer_segment = Column(String, nullable=True)  # 'Företag', 'Privat'
    dealer_group_id = Column(String, nullable=True)

    listing = relationship("Listing", back_populates="car_details")


# ════════════════════════════════════════════════════════════════
# Activity (mutable per-sync state)
# ════════════════════════════════════════════════════════════════
class ListingActivity(Base):
    """Per-sync mutable state for a listing.

    Split from `listings` because last_seen_at is rewritten on
    every sync cycle. Keeping a narrow table means each update
    touches less data.
    """

    __tablename__ = "listing_activity"

    listing_id = Column(
        Integer,
        ForeignKey("listings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    removed_at = Column(DateTime, nullable=True)
    times_reposted = Column(Integer, default=0, nullable=False)

    listing = relationship("Listing", back_populates="activity")


# ════════════════════════════════════════════════════════════════
# Price history (append-only)
# ════════════════════════════════════════════════════════════════
class PriceHistory(Base):
    """Append-only snapshots of a listing's price over time.

    A new row is inserted whenever the observed price differs from
    the most recent one. Lets us detect price drops (both as a UX
    feature and a scam signal).
    """

    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(
        Integer,
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
    )
    price = Column(Numeric(12, 2), nullable=False)
    observed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    listing = relationship("Listing", back_populates="price_history")

    __table_args__ = (
        Index("idx_price_history_listing_time", "listing_id", "observed_at"),
    )


# ════════════════════════════════════════════════════════════════
# Computed features
# ════════════════════════════════════════════════════════════════
class ListingFeatures(Base):
    """Numerical features derived from raw listing data.

    Computed by the feature engineering pipeline and refreshed
    when inputs change (e.g. when category-wide medians shift).
    Kept separate from `listings` so we can recompute without
    touching canonical data.
    """

    __tablename__ = "listing_features"

    listing_id = Column(
        Integer,
        ForeignKey("listings.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # ── Price-related ────────────────────────────────────────────
    price_z_score = Column(Numeric(8, 3), nullable=True)
    price_estimate = Column(Numeric(12, 2), nullable=True)
    price_anomaly = Column(Numeric(8, 3), nullable=True)

    # ── Text-related ─────────────────────────────────────────────
    description_length = Column(Integer, nullable=True)
    title_length = Column(Integer, nullable=True)
    title_caps_ratio = Column(Numeric(5, 4), nullable=True)
    has_urgency_words = Column(Boolean, nullable=True)

    # ── Media-related ────────────────────────────────────────────
    image_count_z = Column(Numeric(8, 3), nullable=True)

    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    listing = relationship("Listing", back_populates="features")


# ════════════════════════════════════════════════════════════════
# Credibility scores (versioned, append-only)
# ════════════════════════════════════════════════════════════════
class CredibilityScore(Base):
    """A scoring run for a listing.

    Scores are never overwritten — every run inserts a new row.
    This lets us:
    - show how a listing's trust changed over time
    - A/B test different scoring algorithms
    - roll back a model_version without losing previous data

    Use a LATERAL JOIN with ORDER BY scored_at DESC LIMIT 1 to
    fetch the latest score for a listing.
    """

    __tablename__ = "credibility_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(
        Integer,
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
    )

    credibility_score = Column(Numeric(4, 2), nullable=False)  # 1.00 .. 10.00
    scam_probability = Column(Numeric(5, 4), nullable=True)    # 0.0000 .. 1.0000
    anomaly_score = Column(Numeric(8, 3), nullable=True)

    # List of triggered flag identifiers and metadata, e.g.
    # [{"code": "price_far_below_median", "flag_type": "red",
    #   "message": "Pris 69% under median", "source": "rules"}]
    reasons = Column(JSON, nullable=False, default=list)

    model_version = Column(String, nullable=False)
    scored_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    listing = relationship("Listing", back_populates="scores")

    __table_args__ = (
        Index("idx_scores_listing_time", "listing_id", "scored_at"),
    )


# ════════════════════════════════════════════════════════════════
# LLM analyses (cache)
# ════════════════════════════════════════════════════════════════
class LLMAnalysis(Base):
    """An OpenAI response cached against the listing it analysed.

    Storing the response as JSON means we can query into specific
    fields (e.g. response->>'verdict') without re-parsing. Type
    discriminates between scam-analysis, price-assessment, etc.
    """

    __tablename__ = "llm_analyses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(
        Integer,
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 'scam_analysis' | 'price_assessment' | 'chat_qa' | ...
    analysis_type = Column(String, nullable=False)
    prompt_version = Column(String, nullable=False)

    # Full structured response from OpenAI
    response = Column(JSON, nullable=False)

    # Token bookkeeping for cost tracking
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    model_name = Column(String, nullable=True)

    analyzed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    listing = relationship("Listing", back_populates="llm_analyses")

    __table_args__ = (
        Index("idx_llm_listing_type", "listing_id", "analysis_type"),
    )


# ════════════════════════════════════════════════════════════════
# Embeddings (pgvector)
# ════════════════════════════════════════════════════════════════
class ListingEmbedding(Base):
    """Vector embedding of a listing's title + description.

    Used for semantic search and similarity-based scam detection.
    Dimension (768) matches KBLab/sentence-bert-swedish-cased.
    If we switch embedding model, regenerate this whole table.
    """

    __tablename__ = "listing_embeddings"

    listing_id = Column(
        Integer,
        ForeignKey("listings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    embedding = Column(Vector(768), nullable=False)
    model_name = Column(String, nullable=False)
    embedded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    listing = relationship("Listing", back_populates="embedding")


# ════════════════════════════════════════════════════════════════
# Saved searches (user-defined watches)
# ════════════════════════════════════════════════════════════════
class SavedSearch(Base):
    """A search the user wants to be notified about.

    For the hackathon we don't have real users; user_id is
    optional so the frontend can create watches anonymously.
    """

    __tablename__ = "saved_searches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=True)
    name = Column(String, nullable=True)
    query_text = Column(Text, nullable=True)

    # Free-form filter dict: {category, max_price, location, ...}
    filters = Column(JSON, nullable=True)

    min_credibility = Column(Numeric(4, 2), nullable=True)
    notify = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ════════════════════════════════════════════════════════════════
# Notifications
# ════════════════════════════════════════════════════════════════
class Notification(Base):
    """A match event between a saved search and a listing.

    Created by the sync worker when a new listing matches an
    existing saved search. Consumed by the frontend's live
    notification panel.
    """

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    saved_search_id = Column(
        Integer,
        ForeignKey("saved_searches.id", ondelete="CASCADE"),
        nullable=False,
    )
    listing_id = Column(
        Integer,
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 'new_match' | 'price_drop' | 'scam_detected'
    notification_type = Column(String, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    seen_at = Column(DateTime, nullable=True)