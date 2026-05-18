"""
FastAPI application entry point.

Wires up CORS, mounts the API router, creates database tables at
startup, and starts the background sync scheduler. Tables creation
is idempotent — only adds what's missing, safe to run on every boot.
In production, use Alembic migrations instead.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import text

from src.api.api import router as api_router
from src.config import settings
from src.db.core import Base, engine
import src.db.models  # noqa: F401 — registers models with Base.metadata
from src.services.scheduler_service import SchedulerService


# Global scheduler reference — lifecycle managed by lifespan
scheduler: SchedulerService | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialise database and start background scheduler.

    On shutdown the scheduler is stopped cleanly so we don't leave
    background tasks running.
    """
    global scheduler

    # ── Database setup ───────────────────────────────────────────
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    logger.info("Database ready")

    # ── Background scheduler ─────────────────────────────────────
    # Skip in DEMO_MODE so the demo presenter can trigger syncs
    # manually for visibility ("watch new listings appear live")
    if not settings.DEMO_MODE:
        scheduler = SchedulerService(
            interval_seconds=settings.SYNC_INTERVAL_SECONDS,
        )
        scheduler.start()
    else:
        logger.info("DEMO_MODE: scheduler disabled, use manual sync")

    yield  # ─── app runs while suspended here ───

    # ── Shutdown ─────────────────────────────────────────────────
    if scheduler:
        scheduler.shutdown()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Hackathon Backend",
    description="Smart search and scam detection on top of Blocket",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — open for hackathon, lock down before any real deploy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness probe — used by Docker healthcheck and demo sanity."""
    return {"status": "ok"}


app.include_router(api_router)
