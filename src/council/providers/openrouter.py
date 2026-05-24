"""OpenRouter API client with per-model concurrency limits and retry backoff."""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Optional

import httpx

from .base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_MAX_RETRIES = 5
_RETRY_BASE_DELAY = 2.0  # seconds — free-tier models need longer backoff


class OpenRouterProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        http_referer: str = "https://github.com/council-agents",
        max_concurrency: int = 1,
        max_backoff: float = 120.0,
    ) -> None:
        self._api_key = api_key
        self._http_referer = http_referer
        self._max_concurrency = max_concurrency
        self._max_backoff = max_backoff
        self._client: Optional[httpx.AsyncClient] = None
        self._model_semaphores: dict[str, asyncio.Semaphore] = {}

    def _get_semaphore(self, model: str) -> asyncio.Semaphore:
        if model not in self._model_semaphores:
            self._model_semaphores[model] = asyncio.Semaphore(self._max_concurrency)
        return self._model_semaphores[model]

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=OPENROUTER_BASE_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "HTTP-Referer": self._http_referer,
                    "Content-Type": "application/json",
                },
                timeout=None,  # We manage timeouts per-call via asyncio.wait_for
            )
        return self._client

    async def call(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        seed: Optional[int] = None,
        timeout: float = 90.0,
        json_mode: bool = False,
        provider_pin: Optional[str] = None,
    ) -> LLMResponse:
        payload: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if seed is not None:
            payload["seed"] = seed
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if provider_pin:
            payload["provider"] = {"order": [provider_pin]}

        last_exc: Exception = RuntimeError("No attempts made")
        sem = self._get_semaphore(model)
        for attempt in range(_MAX_RETRIES):
            try:
                async with sem:
                    response = await asyncio.wait_for(
                        self._post("/chat/completions", payload),
                        timeout=timeout,
                    )
                return self._parse_response(response, model)
            except asyncio.TimeoutError:
                raise  # Don't retry timeouts — caller marks agent abstain
            except RateLimitError as e:
                last_exc = e
                if e.retry_after is not None:
                    delay = min(e.retry_after + random.uniform(0, 1.0), self._max_backoff)
                else:
                    delay = min(
                        _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1.0),
                        self._max_backoff,
                    )
                logger.warning(
                    "rate_limit",
                    extra={"model": model, "attempt": attempt + 1, "retry_in": round(delay, 1)},
                )
                await asyncio.sleep(delay)
            except ModelUnavailableError:
                raise  # Fail fast
            except httpx.HTTPError as e:
                last_exc = e
                delay = min(
                    _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1.0),
                    self._max_backoff,
                )
                logger.warning(
                    "http_error_retry",
                    extra={"model": model, "attempt": attempt + 1, "error": str(e)},
                )
                await asyncio.sleep(delay)

        raise last_exc

    async def _post(self, path: str, payload: dict) -> dict:
        client = self._get_client()
        response = await client.post(path, json=payload)

        if response.status_code == 429:
            retry_after: Optional[float] = None
            if "Retry-After" in response.headers:
                try:
                    retry_after = float(response.headers["Retry-After"])
                except ValueError:
                    pass
            raise RateLimitError(f"Rate limited: {response.text}", retry_after=retry_after)
        if response.status_code == 503:
            raise ModelUnavailableError(f"Model unavailable: {response.text}")
        if response.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code}: {response.text}",
                request=response.request,
                response=response,
            )
        return response.json()

    def _parse_response(self, data: dict, model: str) -> LLMResponse:
        choice = data["choices"][0]
        content = choice["message"]["content"] or ""
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        # OpenRouter returns cost in the usage object
        cost = 0.0
        if "cost" in data:
            cost = float(data["cost"])
        elif "total_cost" in usage:
            cost = float(usage["total_cost"])

        return LLMResponse(
            content=content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            raw=data,
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class RateLimitError(Exception):
    def __init__(self, message: str, retry_after: Optional[float] = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ModelUnavailableError(Exception):
    pass
