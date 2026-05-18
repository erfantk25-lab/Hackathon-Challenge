"""
Sync service — pulls listings from Blocket and stores them in our DB.

Designed to be safe to run repeatedly:
  - Existing listings have their `last_seen_at` updated (and price
    history appended if the price changed)
  - New listings are inserted with full ListingActivity and embedding
  - Pagination is supported per query
  - Rate limiting between calls keeps Blocket happy

The same code path works for initial bulk-fill and for incremental
sync. Just pass different query configs.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from loguru import logger
from sqlalchemy.orm import Session

from blocket_api import BlocketAPI, CarSortOrder

from src.db.core import SessionLocal
from src.db.models import (
    CarDetails,
    Listing,
    ListingActivity,
    ListingEmbedding,
    PriceHistory,
)
from src.services.embedding_service import (
    EMBEDDING_MODEL_NAME,
    embed_batch,
)
from src.services.parsing.cars import parse_car_listing
from src.services.parsing.electronics import parse_electronics_listing

from src.scoring.engine import score_ad
from src.scoring.isolation import detector


# Pause between Blocket API calls to avoid rate limiting
REQUEST_DELAY_SECONDS = 1.0


# ════════════════════════════════════════════════════════════════
# Sync report — what we did this run
# ════════════════════════════════════════════════════════════════
@dataclass
class SyncReport:
    """Summary of one sync run, printed at the end for visibility."""

    new_listings: int = 0
    updated_listings: int = 0
    price_changes: int = 0
    new_embeddings: int = 0
    errors: list[str] = field(default_factory=list)
    total_fetched: int = 0

    def print_summary(self, label: str) -> None:
        logger.info(f"── {label} ─────────────────────────────")
        logger.info(f"  Fetched from Blocket: {self.total_fetched}")
        logger.info(f"  New listings:         {self.new_listings}")
        logger.info(f"  Updated activity:     {self.updated_listings}")
        logger.info(f"  Price changes:        {self.price_changes}")
        logger.info(f"  New embeddings:       {self.new_embeddings}")
        if self.errors:
            logger.warning(f"  Errors:               {len(self.errors)}")
            for err in self.errors[:5]:
                logger.warning(f"    - {err}")


# ════════════════════════════════════════════════════════════════
# Sync service
# ════════════════════════════════════════════════════════════════
class SyncService:
    """Synchronises Blocket data into our database."""

    def __init__(self, api: Optional[BlocketAPI] = None):
        self.api = api or BlocketAPI()

    # ── Public entry points ─────────────────────────────────────
    def sync_electronics(
        self,
        queries: list[dict[str, Any]],
    ) -> SyncReport:
        """Sync electronics listings for each configured query.

        Args:
            queries: List of dicts with keys:
                - 'query' (str): search term
                - 'pages' (int, optional): pagination depth (default 1)
        """
        return self._sync_category(
            category="electronics",
            queries=queries,
            fetch_fn=self._fetch_electronics_page,
            parse_fn=self._parse_electronics_doc,
        )

    def sync_cars(
        self,
        queries: list[dict[str, Any]],
    ) -> SyncReport:
        """Sync car listings for each configured query.

        Args:
            queries: List of dicts with keys:
                - 'query' (str): make to search for
                - 'pages' (int, optional): pagination depth (default 1)
                - 'price_to' (int, optional): max price filter
        """
        return self._sync_category(
            category="cars",
            queries=queries,
            fetch_fn=self._fetch_cars_page,
            parse_fn=self._parse_car_doc,
        )

    # ── Internal: category-agnostic sync flow ───────────────────
    def _sync_category(
        self,
        category: str,
        queries: list[dict[str, Any]],
        fetch_fn: Callable,
        parse_fn: Callable,
    ) -> SyncReport:
        """Generic sync loop that handles fetching, parsing, saving."""
        report = SyncReport()
        all_parsed: list[tuple[dict, Optional[dict]]] = []

        # ── Phase 1: fetch and parse all docs ───────────────────
        for q in queries:
            query_str = q["query"]
            pages = q.get("pages", 1)

            for page in range(1, pages + 1):
                logger.info(f"  Fetching '{query_str}' page {page}/{pages}...")
                try:
                    docs = fetch_fn(q, page)
                except Exception as e:
                    msg = f"fetch '{query_str}' page {page}: {e}"
                    logger.error(msg)
                    report.errors.append(msg)
                    continue

                report.total_fetched += len(docs)
                logger.info(f"    got {len(docs)} docs")

                # Parse each doc; collect for batch processing
                for doc in docs:
                    try:
                        parsed = parse_fn(doc)
                        all_parsed.append(parsed)
                    except Exception as e:
                        ad_id = doc.get("ad_id", "?")
                        msg = f"parse ad_id={ad_id}: {e}"
                        logger.warning(msg)
                        report.errors.append(msg)

                # Be kind to Blocket between requests
                time.sleep(REQUEST_DELAY_SECONDS)

        # ── Phase 2: persist to database ────────────────────────
        logger.info(f"  Persisting {len(all_parsed)} parsed listings...")
        self._persist_listings(all_parsed, report)

        return report

    # ── Fetch wrappers (one per category) ───────────────────────
    def _fetch_electronics_page(
        self,
        query_config: dict,
        page: int,
    ) -> list[dict]:
        """Call api.search() and extract the docs list."""
        response = self.api.search(
            query_config["query"],
            page=page,
        )
        return response.get("docs", []) or []

    def _fetch_cars_page(
        self,
        query_config: dict,
        page: int,
    ) -> list[dict]:
        """Call api.search_car() with optional filters."""
        kwargs: dict[str, Any] = {
            "page": page,
            "sort_order": CarSortOrder.RELEVANCE,
        }
        if "price_to" in query_config:
            kwargs["price_to"] = query_config["price_to"]
        if "price_from" in query_config:
            kwargs["price_from"] = query_config["price_from"]

        response = self.api.search_car(query_config["query"], **kwargs)
        return response.get("docs", []) or []

    # ── Parse wrappers (normalise to common shape) ──────────────
    def _parse_electronics_doc(
        self,
        doc: dict,
    ) -> tuple[dict, Optional[dict]]:
        """Returns (listing_dict, None) — electronics has no sidecar."""
        return parse_electronics_listing(doc), None

    def _parse_car_doc(
        self,
        doc: dict,
    ) -> tuple[dict, dict]:
        """Returns (listing_dict, car_details_dict)."""
        return parse_car_listing(doc)

    # ── Phase 2 internals: writing to the database ──────────────
    def _persist_listings(
        self,
        parsed: list[tuple[dict, Optional[dict]]],
        report: SyncReport,
    ) -> None:
        """Upsert listings and queue new ones for embedding."""
        db: Session = SessionLocal()
        new_listing_ids: list[tuple[int, str]] = []  # (id, text-to-embed)

        try:
            for listing_kwargs, car_details_kwargs in parsed:
                blocket_id = listing_kwargs["blocket_id"]

                existing = (
                    db.query(Listing).filter(Listing.blocket_id == blocket_id).first()
                )

                if existing:
                    # ── Update existing listing ─────────────────
                    self._update_existing(existing, listing_kwargs, db, report)
                else:
                    # ── Insert new listing ──────────────────────
                    new_listing = self._insert_new(
                        listing_kwargs,
                        car_details_kwargs,
                        db,
                    )
                    db.flush()  # populate new_listing.id for FKs

                    # Track for embedding (heading + description if any)
                    text_to_embed = self._build_embedding_text(listing_kwargs)
                    new_listing_ids.append((new_listing.id, text_to_embed))

                    report.new_listings += 1

            db.commit()

            # ── Phase 3: batch-embed new listings ───────────────
            if new_listing_ids:
                self._embed_new_listings(new_listing_ids, db, report)
                db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"Persist failed: {e}")
            report.errors.append(f"persist: {e}")
            raise
        finally:
            db.close()

    def _insert_new(
        self,
        listing_kwargs: dict,
        car_details_kwargs: Optional[dict],
        db: Session,
    ) -> Listing:
        """Create Listing + ListingActivity + PriceHistory (+ CarDetails)."""
        listing = Listing(**listing_kwargs)
        db.add(listing)
        db.flush()  # need id for related rows

        # Always create activity row
        db.add(
            ListingActivity(
                listing_id=listing.id,
                last_seen_at=datetime.utcnow(),
                is_active=True,
            )
        )

        # Initial price snapshot
        if listing.price is not None:
            db.add(
                PriceHistory(
                    listing_id=listing.id,
                    price=listing.price,
                )
            )

        # Car-specific sidecar
        if car_details_kwargs:
            db.add(CarDetails(listing_id=listing.id, **car_details_kwargs))

        return listing

    def _update_existing(
        self,
        existing: Listing,
        listing_kwargs: dict,
        db: Session,
        report: SyncReport,
    ) -> None:
        """Touch last_seen_at and record price change if applicable."""
        # Update activity
        if existing.activity:
            existing.activity.last_seen_at = datetime.utcnow()
            existing.activity.is_active = True
        else:
            db.add(
                ListingActivity(
                    listing_id=existing.id,
                    last_seen_at=datetime.utcnow(),
                    is_active=True,
                )
            )

        # Record price change if it differs from current
        new_price = listing_kwargs.get("price")
        if new_price is not None and existing.price != new_price:
            db.add(
                PriceHistory(
                    listing_id=existing.id,
                    price=new_price,
                )
            )
            existing.price = new_price
            report.price_changes += 1

        report.updated_listings += 1

    def _build_embedding_text(self, listing_kwargs: dict) -> str:
        """Combine heading and description for the embedding model.

        Description is usually None in fresh listings (only filled in
        by a separate get_ad() pass), so we mostly embed the heading.
        """
        parts = [listing_kwargs.get("heading", "")]
        if listing_kwargs.get("description"):
            parts.append(listing_kwargs["description"])
        return "\n".join(p for p in parts if p)

    def _embed_new_listings(
        self,
        new_listings: list[tuple[int, str]],
        db: Session,
        report: SyncReport,
    ) -> None:
        """Generate embeddings for new listings in a single batch."""
        listing_ids = [lid for lid, _ in new_listings]
        texts = [text for _, text in new_listings]

        logger.info(f"  Embedding {len(texts)} new listings in batch...")
        vectors = embed_batch(texts)

        for listing_id, vector in zip(listing_ids, vectors):
            db.add(
                ListingEmbedding(
                    listing_id=listing_id,
                    embedding=vector,
                    model_name=EMBEDDING_MODEL_NAME,
                )
            )

        report.new_embeddings = len(vectors)
