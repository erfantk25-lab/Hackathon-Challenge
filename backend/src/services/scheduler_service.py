"""
Background scheduler for periodic sync.

Uses APScheduler to run sync_service in the background. Started by
FastAPI's lifespan handler, shut down cleanly on application exit.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from src.services.sync_service import SyncService


# What to sync on each scheduled tick. Kept small so each run is
# fast — we're catching new listings, not doing bulk fills.
RECURRING_ELECTRONICS = [
    {"query": "iphone", "pages": 1},
    {"query": "macbook", "pages": 1},
    {"query": "playstation 5", "pages": 1},
]

RECURRING_CARS = [
    {"query": "volvo", "pages": 1, "price_to": 200_000},
    {"query": "audi", "pages": 1, "price_to": 200_000},
]


class SchedulerService:
    """Wraps APScheduler to run recurring sync jobs."""

    def __init__(self, interval_seconds: int = 30):
        self.interval_seconds = interval_seconds
        self.scheduler = AsyncIOScheduler()
        self.sync_service = SyncService()

    def start(self) -> None:
        """Begin scheduled execution."""
        self.scheduler.add_job(
            self._tick,
            trigger=IntervalTrigger(seconds=self.interval_seconds),
            id="sync_tick",
            max_instances=1,  # don't pile up if a tick runs long
            coalesce=True,  # if missed several ticks, run only once
        )
        self.scheduler.start()
        logger.info(f"Scheduler started — sync every {self.interval_seconds}s")

    def shutdown(self) -> None:
        """Stop the scheduler cleanly."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    def _tick(self) -> None:
        """One scheduled sync run."""
        logger.info("Scheduled sync tick starting...")
        try:
            electronics_report = self.sync_service.sync_electronics(
                RECURRING_ELECTRONICS
            )
            cars_report = self.sync_service.sync_cars(RECURRING_CARS)

            total_new = electronics_report.new_listings + cars_report.new_listings
            if total_new > 0:
                logger.info(f"Scheduled sync: {total_new} new listings")
            else:
                logger.info("Scheduled sync: no new listings")

        except Exception as e:
            logger.error(f"Scheduled sync failed: {e}")
