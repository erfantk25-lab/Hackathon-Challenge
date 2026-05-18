"""
Manually trigger scoring on all active listings.

Run with:
    python scripts/score_all.py
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from loguru import logger

from src.services.scoring.scoring_service import ScoringService


def main() -> None:
    logger.info("=" * 60)
    logger.info("Starting scoring run")
    logger.info("=" * 60)

    service = ScoringService()
    report = service.score_all_active()
    report.print_summary()

    logger.info("=" * 60)
    logger.info("Done.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
