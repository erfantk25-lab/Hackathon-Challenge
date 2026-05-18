from contextlib import asynccontextmanager
from src.db.core import engine, Base
import src.db.models  # noqa: F401 — registers models

@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup: ensure tables exist. Idempotent — only creates
    # what's missing. In production you'd use Alembic instead.
    Base.metadata.create_all(bind=engine)
    yield
    # On shutdown: nothing for now

app = FastAPI(title="Hackathon Backend", lifespan=lifespan)