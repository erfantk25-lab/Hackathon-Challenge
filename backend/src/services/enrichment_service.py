"""
Enrichment service — fetches detailed descriptions via api.get_ad().

The Blocket search endpoint returns metadata but not full descriptions.
This service fetches them lazily for listings where description is None,
and regenerates the embedding with the richer text.

Run periodically (or on-demand) to fill in missing descriptions.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from loguru import logger
from sqlalchemy.orm import Session

from blocket_api import BlocketAPI, CarAd, RecommerceAd

from src.db.core import SessionLocal
from src.db.models import Listing, ListingEmbedding
from src.services.embedding_service import (
    EMBEDDING_MODEL_NAME,
    embed_text,
)


# Delay between get_ad calls to avoid rate limiting
REQUEST_DELAY_SECONDS = 0.5


@dataclass
class EnrichmentReport:
    """Summary of one enrichment run."""

    enriched: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def print_summary(self) -> None:
        logger.info("── ENRICHMENT ─────────────────────────────")
        logger.info(f"  Enriched: {self.enriched}")
        logger.info(f"  Skipped:  {self.skipped}")
        if self.errors:
            logger.warning(f"  Errors:   {len(self.errors)}")
            for err in self.errors[:5]:
                logger.warning(f"    - {err}")


class EnrichmentService:
    """Lazy-loads full descriptions for listings via get_ad()."""

    def __init__(self, api: Optional[BlocketAPI] = None):
        self.api = api or BlocketAPI()

    def enrich_missing_descriptions(
        self,
        batch_size: int = 50,
    ) -> EnrichmentReport:
        """Fetch descriptions for active listings where description IS NULL.

        Skips listings already marked inactive (e.g. those that returned
        404 on a previous enrichment attempt). Updates listing.description
        and regenerates the embedding with the richer (heading + description)
        text.
        """
        from src.db.models import ListingActivity

        report = EnrichmentReport()
        db: Session = SessionLocal()

        try:
            # Find active listings without descriptions
            listings = (
                db.query(Listing)
                .join(ListingActivity, ListingActivity.listing_id == Listing.id)
                .filter(Listing.description.is_(None))
                .filter(ListingActivity.is_active.is_(True))
                .limit(batch_size)
                .all()
            )

            if not listings:
                logger.info("No active listings need enrichment")
                return report

            logger.info(f"Enriching {len(listings)} listings...")

            for listing in listings:
                try:
                    self._enrich_one(listing, db)
                    report.enriched += 1

                    # Print progress every 10
                    if report.enriched % 10 == 0:
                        logger.info(f"  Progress: {report.enriched}/{len(listings)}")

                except Exception as e:
                    msg = f"listing {listing.id} (blocket_id={listing.blocket_id}): {e}"
                    logger.warning(msg)
                    report.errors.append(msg)
                    report.skipped += 1

                time.sleep(REQUEST_DELAY_SECONDS)

            db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"Enrichment failed: {e}")
            report.errors.append(f"batch: {e}")
            raise
        finally:
            db.close()

        return report

    def _enrich_one(self, listing: Listing, db: Session) -> None:
        """Fetch description for one listing and update DB.

        Handles 404 gracefully — listings removed from Blocket are
        marked as inactive so we don't retry them.
        """
        blocket_id_int = int(listing.blocket_id)

        if listing.category == "cars":
            ad_obj = CarAd(blocket_id_int)
        else:
            ad_obj = RecommerceAd(blocket_id_int)

        try:
            detail = self.api.get_ad(ad_obj)
        except Exception as e:
            # Most common: HTTPStatusError 404 (listing removed from Blocket).
            # Mark as inactive so we don't retry.
            if "404" in str(e):
                if listing.activity:
                    listing.activity.is_active = False
                logger.info(f"  Listing {listing.id} marked inactive (404)")
                return
            # Other errors — re-raise so caller logs them
            raise

        description = self._extract_description(detail, listing.category)

        if not description:
            return

        listing.description = description
        listing.description_fetched_at = datetime.utcnow()

        embedding_text = f"{listing.heading}\n{description}"
        new_vector = embed_text(embedding_text)

        existing_embedding = (
            db.query(ListingEmbedding)
            .filter(ListingEmbedding.listing_id == listing.id)
            .first()
        )

        if existing_embedding:
            existing_embedding.embedding = new_vector
            existing_embedding.model_name = EMBEDDING_MODEL_NAME
            existing_embedding.embedded_at = datetime.utcnow()
        else:
            db.add(
                ListingEmbedding(
                    listing_id=listing.id,
                    embedding=new_vector,
                    model_name=EMBEDDING_MODEL_NAME,
                )
            )

    def _extract_description(
        self,
        detail: dict[str, Any],
        category: str,
    ) -> Optional[str]:
        """Pull description from the nested Remix loaderData structure.

        Blocket's detail endpoint returns a complex nested structure.
        We navigate it carefully and fall back to None if any layer
        is missing.
        """
        if not detail:
            return None

        # Try multiple paths since the structure varies
        candidates = [
            # Recommerce (electronics) path
            ("loaderData", "item-recommerce", "itemData", "description"),
            # Cars path — try common variants
            ("loaderData", "item-mobility", "itemData", "description"),
            ("loaderData", "item-mobility", "itemData", "body"),
            # Generic fallbacks
            ("item", "description"),
            ("description",),
            ("body",),
        ]

        for path in candidates:
            value = detail
            for key in path:
                if not isinstance(value, dict):
                    value = None
                    break
                value = value.get(key)
                if value is None:
                    break

            if isinstance(value, str) and value.strip():
                return value.strip()

        return None
