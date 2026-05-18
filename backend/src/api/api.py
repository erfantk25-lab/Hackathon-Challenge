from fastapi import APIRouter

from src.api.router.embedded_model import router as ai_router
from src.api.router.search import router as search_router

router = APIRouter()
router.include_router(search_router)
router.include_router(ai_router)
