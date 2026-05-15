from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class Embedder(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_one(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0]


class OpenAIEmbedder(Embedder):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        self._api_key = api_key
        self._model = model
        self._client: Optional[object] = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._get_client()
        response = await client.embeddings.create(input=texts, model=self._model)
        return [item.embedding for item in response.data]


class OpenRouterEmbedder(Embedder):
    """Embeddings via OpenRouter using OpenAI-compat endpoint."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        import httpx
        self._api_key = api_key
        self._model = model
        self._client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.post(
            "/embeddings",
            json={"model": self._model, "input": texts},
        )
        response.raise_for_status()
        data = response.json()
        return [item["embedding"] for item in data["data"]]


class LocalEmbedder(Embedder):
    """Local embeddings via sentence-transformers. No API key, no rate limits."""

    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model
        self._model = None  # lazy-load on first use

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("local_embedder_loading_model", extra={"model": self._model_name})
            self._model = SentenceTransformer(self._model_name)
        return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import asyncio
        loop = asyncio.get_event_loop()
        # Run CPU-bound encoding in a thread pool so it doesn't block the event loop
        model = self._get_model()
        embeddings = await loop.run_in_executor(None, lambda: model.encode(texts).tolist())
        return embeddings


class NullEmbedder(Embedder):
    """Fallback embedder that always returns zero vectors (triggers exact-text matching)."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 1536 for _ in texts]


def build_embedder(
    provider: str,
    model: str,
    openai_api_key: Optional[str],
    openrouter_api_key: Optional[str],
) -> Embedder:
    if provider == "none":
        logger.info("embedder_disabled_using_exact_text_matching")
        return NullEmbedder()
    if provider == "local":
        return LocalEmbedder(model=model)
    if provider == "openai":
        if not openai_api_key:
            logger.warning(
                "no_openai_key_falling_back_to_null_embedder",
                extra={"detail": "Set OPENAI_API_KEY for semantic deduplication"},
            )
            return NullEmbedder()
        return OpenAIEmbedder(api_key=openai_api_key, model=model)
    elif provider == "openrouter":
        if not openrouter_api_key:
            logger.warning("no_openrouter_key_falling_back_to_null_embedder")
            return NullEmbedder()
        return OpenRouterEmbedder(api_key=openrouter_api_key, model=model)
    else:
        raise ValueError(f"Unknown embedder provider: {provider}")
