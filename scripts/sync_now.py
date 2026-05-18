"""
Manually trigger a sync run.

For hackathon-time work: edit the query configs below and run this
script to fill the database. Later we'll wire this into APScheduler
for automatic recurring sync, but for now manual is simpler.

Run with:
    python scripts/sync_now.py
"""

import sys
from pathlib import Path

# Make src/ importable regardless of cwd
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from loguru import logger

from src.services.sync_service import SyncService


# ════════════════════════════════════════════════════════════════
# Query configuration
# ════════════════════════════════════════════════════════════════
# Start small to verify the pipeline works end-to-end. Once you
# see ~50 listings in the DB and embeddings generated, switch to
# BIG_* configs below for the full population.

SMALL_ELECTRONICS = [
    {"query": "iphone", "pages": 1},
]

SMALL_CARS = [
    {"query": "volvo", "pages": 1, "price_to": 200_000},
]

# ── Full hackathon-scale config ─────────────────────────────────
BIG_ELECTRONICS = [
    {"query": "iphone", "pages": 3},
    {"query": "samsung galaxy", "pages": 2},
    {"query": "macbook", "pages": 2},
    {"query": "ipad", "pages": 2},
    {"query": "playstation 5", "pages": 2},
    {"query": "xbox", "pages": 1},
    {"query": "airpods", "pages": 1},
    {"query": "nintendo switch", "pages": 1},
    {"query": "apple watch", "pages": 1},
    {"query": "dyson", "pages": 1},
]

BIG_CARS = [
    {"query": "volvo", "pages": 2, "price_to": 200_000},
    {"query": "audi", "pages": 2, "price_to": 200_000},
    {"query": "bmw", "pages": 2, "price_to": 200_000},
    {"query": "mercedes", "pages": 2, "price_to": 200_000},
    {"query": "volkswagen", "pages": 2, "price_to": 200_000},
    {"query": "toyota", "pages": 2, "price_to": 200_000},
    {"query": "skoda", "pages": 2, "price_to": 200_000},
    {"query": "ford", "pages": 2, "price_to": 200_000},
    {"query": "kia", "pages": 2, "price_to": 200_000},
    {"query": "hyundai", "pages": 2, "price_to": 200_000},
    {"query": "tesla", "pages": 2, "price_to": 200_000},
    {"query": "peugeot", "pages": 1, "price_to": 200_000},
    {"query": "renault", "pages": 1, "price_to": 200_000},
    {"query": "nissan", "pages": 1, "price_to": 200_000},
    {"query": "mazda", "pages": 1, "price_to": 200_000},
    {"query": "honda", "pages": 1, "price_to": 200_000},
    {"query": "opel", "pages": 1, "price_to": 200_000},
]


# ════════════════════════════════════════════════════════════════
# Run the sync
# ════════════════════════════════════════════════════════════════
def main() -> None:
    # ── Toggle: use SMALL_* first to verify, then BIG_* ─────────
    use_big = False  # ← flip to True after verifying with SMALL

    if use_big:
        electronics_queries = BIG_ELECTRONICS
        car_queries = BIG_CARS
        logger.info("Running BIG sync configuration")
    else:
        electronics_queries = SMALL_ELECTRONICS
        car_queries = SMALL_CARS
        logger.info("Running SMALL sync configuration (verify mode)")

    service = SyncService()

    logger.info("=" * 60)
    logger.info("Starting electronics sync...")
    logger.info("=" * 60)
    electronics_report = service.sync_electronics(electronics_queries)
    electronics_report.print_summary("ELECTRONICS")

    logger.info("=" * 60)
    logger.info("Starting cars sync...")
    logger.info("=" * 60)
    cars_report = service.sync_cars(car_queries)
    cars_report.print_summary("CARS")

    logger.info("=" * 60)
    logger.info("Sync complete.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
