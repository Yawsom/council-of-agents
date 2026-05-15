from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    raw: dict = field(default_factory=dict)


class LLMProvider(ABC):
    @abstractmethod
    async def call(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        seed: Optional[int] = None,
        timeout: float = 90.0,
        json_mode: bool = False,
        provider_pin: Optional[str] = None,
    ) -> LLMResponse: ...
