"""
FastAPI application entry point.

Wires up CORS, mounts the API router, and creates database tables
at startup. Tables creation is idempotent — only adds what's missing,
safe to run on every boot. In production, use Alembic migrations
instead.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.api.api import router as api_router
from src.db.core import Base, engine
import src.db.models  # noqa: F401 — registers models with Base.metadata


@asynccontextmanager
async def lifespan(_app: FastAPI):
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    yield

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
