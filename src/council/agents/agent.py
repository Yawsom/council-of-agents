"""Council member (SubAgent) — LLM calls, cost tracking, and exclusion state.

SubAgent is the runtime wrapper for debating agents. It does not parse responses;
orchestration/ handles parsing and graph ingestion after each call.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from ..config.schema import AgentConfig
from ..providers.base import LLMProvider, LLMResponse
from .parser import ParseError, SchemaError

logger = logging.getLogger(__name__)

REFORMAT_MESSAGE = (
    "Your previous response was not valid JSON. "
    "Please reformat it as valid JSON exactly matching the required schema. "
    "Output ONLY the JSON object, nothing else."
)


@dataclass
class AgentCallResult:
    agent_id: str
    response: Optional[LLMResponse]
    abstained: bool = False
    abstain_reason: str = ""
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class SubAgent:
    """A council member that calls an LLM and tracks its claims and costs."""

    def __init__(self, config: AgentConfig, provider: LLMProvider) -> None:
        self.config = config
        self.provider = provider
        self.id = config.id
        self.model = config.model

        # Tracks all claim IDs proposed by this agent across rounds
        self.claim_ids: set[str] = set()
        # Tracks all falsifiers committed across rounds
        self.falsifier_history: list[str] = []
        # Per-round cost tracking
        self.cost_log: list[dict] = []
        # Once True, this agent is skipped for all subsequent phases/rounds
        self.excluded: bool = False

    async def call(
        self,
        messages: list[dict],
        round_num: int,
        system: Optional[str] = None,
    ) -> AgentCallResult:
        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        try:
            response = await self.provider.call(
                messages=full_messages,
                model=self.model,
                temperature=self.config.temperature,
                seed=self.config.seed,
                timeout=self.config.timeout,
                json_mode=True,
                provider_pin=self.config.provider_pin,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "agent_timeout",
                extra={"agent_id": self.id, "round": round_num, "model": self.model},
            )
            return AgentCallResult(
                agent_id=self.id,
                response=None,
                abstained=True,
                abstain_reason="timeout",
            )
        except Exception as e:
            logger.warning(
                "agent_api_error",
                extra={"agent_id": self.id, "round": round_num, "model": self.model, "error": str(e)[:200]},
            )
            return AgentCallResult(
                agent_id=self.id,
                response=None,
                abstained=True,
                abstain_reason=f"api_error: {type(e).__name__}",
            )

        self._log_cost(response, round_num)
        return AgentCallResult(
            agent_id=self.id,
            response=response,
            abstained=False,
            cost_usd=response.cost_usd,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
        )

    async def call_with_retry_on_malformed(
        self,
        messages: list[dict],
        round_num: int,
        system: Optional[str] = None,
    ) -> AgentCallResult:
        """Call once; on ParseError/SchemaError retry once with reformat message; then abstain."""
        result = await self.call(messages, round_num, system)
        if result.abstained:
            return result

        # Caller will parse; if parsing fails they should call this variant which
        # handles the single retry automatically.
        # Here we return the raw result; retry logic is in orchestration.
        return result

    async def retry_with_reformat(
        self,
        original_messages: list[dict],
        original_response_content: str,
        round_num: int,
        system: Optional[str] = None,
    ) -> AgentCallResult:
        """Send a reformat request and return the new response."""
        retry_messages = list(original_messages) + [
            {"role": "assistant", "content": original_response_content},
            {"role": "user", "content": REFORMAT_MESSAGE},
        ]
        return await self.call(retry_messages, round_num, system)

    def _log_cost(self, response: LLMResponse, round_num: int) -> None:
        self.cost_log.append({
            "round": round_num,
            "model": self.model,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "cost_usd": response.cost_usd,
        })

    def total_cost(self) -> float:
        return sum(e["cost_usd"] for e in self.cost_log)
