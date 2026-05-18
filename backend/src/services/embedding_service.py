from openai import AsyncOpenAI

from src.config import settings

EMBEDDING_MODEL_NAME = settings.EMBEDDING_MODEL
EMBEDDING_DIMENSION = settings.EMBEDDING_DIMENSIONS


def get_ai_client() -> AsyncOpenAI:
    kwargs = {"api_key": settings.ai_api_key}
    if settings.ai_base_url:
        kwargs["base_url"] = settings.ai_base_url
    return AsyncOpenAI(**kwargs)


def listing_text(listing) -> str:
    parts = [
        listing.heading or "",
        listing.description or "",
        str(listing.price or ""),
        listing.location or "",
        listing.category or "",
    ]
    return "\n".join(part for part in parts if part).strip()


async def embed_text(text: str) -> list[float]:
    text = (text or "").strip()
    if not text:
        text = "empty listing"

    response = await get_ai_client().embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=text,
    )
    return _validate_embedding(response.data[0].embedding)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    cleaned = [(text or "empty listing").strip() or "empty listing" for text in texts]
    if not cleaned:
        return []

    response = await get_ai_client().embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=cleaned,
    )
    return [_validate_embedding(item.embedding) for item in response.data]


def _validate_embedding(vector: list[float]) -> list[float]:
    if len(vector) != settings.EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Embedding model {settings.EMBEDDING_MODEL!r} returned "
            f"{len(vector)} dimensions, expected {settings.EMBEDDING_DIMENSIONS}."
        )
    return vector
