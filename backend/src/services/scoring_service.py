"""
Scoring service — runs scoring on all active listings and persists.

Orchestrates the rule-based + isolation forest pipeline from
src/scoring/engine.py and writes results to credibility_scores.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from loguru import logger
from sqlalchemy.orm import Session

from src.db.core import SessionLocal
from src.db.models import CredibilityScore, Listing, ListingActivity

# Adjust this import path to match where the engine actually lives
# In kollegan's code it's `src.scoring.engine`. If you moved it to
# src.services.scoring.engine, change this line.
from src.scoring.engine import score_ad
from src.scoring.isolation import detector


MODEL_VERSION = "v1.0-rules"


@dataclass
class ScoringReport:
    """Summary of one scoring run."""

    scored: int = 0
    errors: list[str] = field(default_factory=list)

    def print_summary(self) -> None:
        logger.info("── SCORING ─────────────────────────────")
        logger.info(f"  Scored: {self.scored}")
        if self.errors:
            logger.warning(f"  Errors: {len(self.errors)}")
            for err in self.errors[:5]:
                logger.warning(f"    - {err}")


class ScoringService:
    """Runs scoring on listings and persists results."""

    def score_all_active(self) -> ScoringReport:
        """Score every active listing and write CredibilityScore rows.

        Fits the isolation forest on all listings first (so it has
        baseline statistics), then scores each one and persists.
        """
        report = ScoringReport()
        db: Session = SessionLocal()

        try:
            # ── Fetch active listings ────────────────────────
            listings = (
                db.query(Listing)
                .join(ListingActivity, ListingActivity.listing_id == Listing.id)
                .filter(ListingActivity.is_active.is_(True))
                .all()
            )

            if not listings:
                logger.info("No active listings to score")
                return report

            logger.info(f"Scoring {len(listings)} active listings...")

            # ── Fit isolation forest on all current data ─────
            # This means anomalies are relative to the current
            # population — outliers in the dataset we have now.
            detector.fit(listings)

            # ── Score each listing ───────────────────────────
            now = datetime.utcnow()

            for listing in listings:
                try:
                    output = score_ad(listing)

                    db.add(
                        CredibilityScore(
                            listing_id=listing.id,
                            credibility_score=Decimal(str(output.score)),
                            scam_probability=(
                                Decimal("1.0")
                                - Decimal(str(output.score)) / Decimal("10")
                                if output.is_suspicious
                                else None
                            ),
                            reasons=output.reasons,
                            model_version=MODEL_VERSION,
                            scored_at=now,
                        )
                    )

                    report.scored += 1

                    if report.scored % 25 == 0:
                        logger.info(f"  Progress: {report.scored}/{len(listings)}")

                except Exception as e:
                    msg = f"listing {listing.id}: {type(e).__name__}: {e}"
                    logger.warning(msg)
                    report.errors.append(msg)

            db.commit()
            logger.info(f"  Committed {report.scored} scores to database")

        except Exception as e:
            db.rollback()
            logger.error(f"Scoring failed: {e}")
            report.errors.append(f"batch: {e}")
            raise
        finally:
            db.close()

        return report
