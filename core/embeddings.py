"""Voyage AI embedding client — generates 512-dim vectors for semantic search."""

import os
import logging
import httpx

logger = logging.getLogger(__name__)

VOYAGE_API_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-3-lite"
VOYAGE_DIMENSIONS = 512

_api_key: str | None = None


def _get_api_key() -> str | None:
    global _api_key
    if _api_key is None:
        _api_key = os.getenv("VOYAGE_API_KEY", "")
    return _api_key or None


def embed_text(text: str) -> list[float] | None:
    """Embed a single text string. Returns 512-dim vector or None on failure."""
    result = embed_batch([text])
    if result and result[0]:
        return result[0]
    return None


def embed_batch(texts: list[str]) -> list[list[float] | None] | None:
    """Embed up to 128 texts in one API call. Returns list of vectors or None."""
    api_key = _get_api_key()
    if not api_key:
        logger.warning("VOYAGE_API_KEY not set — skipping embedding generation")
        return None

    if not texts:
        return []

    # Voyage AI batch limit is 128
    if len(texts) > 128:
        texts = texts[:128]

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                VOYAGE_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": texts,
                    "model": VOYAGE_MODEL,
                },
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]
    except Exception as e:
        logger.warning(f"Embedding generation failed: {e}")
        return None
