"""
Manually trigger description enrichment.

Run with:
    python scripts/enrich_descriptions.py

Default batch size is 50. Edit BATCH_SIZE below for more/fewer.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from loguru import logger

from src.services.enrichment_service import EnrichmentService


BATCH_SIZE = 50


def main() -> None:
    logger.info("=" * 60)
    logger.info(f"Starting enrichment (batch size: {BATCH_SIZE})")
    logger.info("=" * 60)

    service = EnrichmentService()
    report = service.enrich_missing_descriptions(batch_size=BATCH_SIZE)
    report.print_summary()

    logger.info("=" * 60)
    logger.info("Done.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
