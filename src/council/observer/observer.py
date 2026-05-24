"""Observer — auditor for agent faithfulness and verdict grounding.

Runs during Phase 2 (agent_faithfulness) and Phase 3 (verdict_grounding).
Can abort a run if it detects critical inconsistencies.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from ..agents.parser import ObserverResponse, ParseError, SchemaError, parse_observer
from ..agents.prompts import OBSERVER_SYSTEM, observer_user
from ..graph.graph import ClaimGraph
from ..graph.serializer import serialize_open_state
from ..providers.base import LLMProvider

logger = logging.getLogger(__name__)

OBSERVER_AGENT_ID = "observer"


@dataclass
class ObserverCheckResult:
    response: Optional[ObserverResponse]
    abstained: bool = False
    cost_usd: float = 0.0


class Observer:
    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        temperature: float = 0.2,
        seed: Optional[int] = None,
        timeout: float = 60.0,
    ) -> None:
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.timeout = timeout
        self.log: list[dict] = []
        self.cost_log: list[dict] = []

    async def check(
        self,
        round_num: int,
        check_type: str,
        subject_id: str,
        graph: ClaimGraph,
        subject_output: str,
    ) -> ObserverCheckResult:
        graph_state = serialize_open_state(graph, OBSERVER_AGENT_ID)
        user_content = observer_user(
            round_num=round_num,
            check_type=check_type,
            subject_id=subject_id,
            graph_state=graph_state,
            subject_output=subject_output,
        )
        messages = [
            {"role": "system", "content": OBSERVER_SYSTEM},
            {"role": "user", "content": user_content},
        ]

        try:
            llm_response = await asyncio.wait_for(
                self.provider.call(
                    messages=messages,
                    model=self.model,
                    temperature=self.temperature,
                    seed=self.seed,
                    timeout=self.timeout,
                    json_mode=True,
                ),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "observer_timeout",
                extra={"round": round_num, "check_type": check_type},
            )
            return ObserverCheckResult(response=None, abstained=True)
        except Exception as e:
            logger.warning(
                "observer_error",
                extra={"round": round_num, "check_type": check_type, "error": str(e)[:200]},
            )
            return ObserverCheckResult(response=None, abstained=True)

        self.cost_log.append({
            "round": round_num,
            "check_type": check_type,
            "cost_usd": llm_response.cost_usd,
        })

        try:
            parsed = parse_observer(llm_response.content, round_num)
        except (ParseError, SchemaError) as e:
            logger.warning(
                "observer_parse_error",
                extra={"round": round_num, "error": str(e)},
            )
            return ObserverCheckResult(response=None, abstained=True)

        self.log.append(parsed.raw)
        self._emit_log(parsed)
        return ObserverCheckResult(response=parsed, cost_usd=llm_response.cost_usd)

    def _emit_log(self, obs: ObserverResponse) -> None:
        for issue in obs.issues:
            level = logging.ERROR if issue.get("severity") == "error" else logging.WARNING
            logger.log(
                level,
                "observer_issue",
                extra={
                    "round": obs.round,
                    "check_type": obs.check_type,
                    "subject": obs.subject_id,
                    "severity": issue.get("severity"),
                    "description": issue.get("description"),
                },
            )

    def should_abort(self, result: ObserverCheckResult) -> bool:
        if result.abstained or result.response is None:
            return False
        obs = result.response
        has_error = any(i.get("severity") == "error" for i in obs.issues)
        return has_error and obs.recommended_action == "abort"

    def total_cost(self) -> float:
        return sum(e["cost_usd"] for e in self.cost_log)
