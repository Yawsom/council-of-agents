from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from ..agents.agent import SubAgent
from ..agents.parser import ParseError, SchemaError, VerdictResponse, parse_verdict
from ..agents.prompts import PHASE3_SYSTEM, phase3_user
from ..graph.graph import ClaimGraph
from ..graph.serializer import serialize_open_state
from ..observer.observer import Observer

logger = logging.getLogger(__name__)


@dataclass
class Phase3Result:
    verdicts: list[VerdictResponse]
    abstained_agents: list[str] = field(default_factory=list)
    observer_issues: list[dict] = field(default_factory=list)


async def _stagger_gather(coroutines: list, stagger_delay: float) -> list:
    tasks = []
    for i, coro in enumerate(coroutines):
        if i > 0 and stagger_delay > 0:
            await asyncio.sleep(stagger_delay)
        tasks.append(asyncio.create_task(coro))
    return list(await asyncio.gather(*tasks, return_exceptions=True))


async def run_phase3(
    question: str,
    agents: list[SubAgent],
    graph: ClaimGraph,
    observer: Optional[Observer] = None,
    artifacts_writer=None,
    stagger_delay: float = 0.0,
) -> Phase3Result:
    known_ids = {n.id for n in graph.claims + graph.evidence + graph.assumptions}
    active_agents = [a for a in agents if not a.excluded]

    results = await _stagger_gather(
        [_call_agent_phase3(agent, question, graph, known_ids) for agent in active_agents],
        stagger_delay,
    )

    verdicts: list[VerdictResponse] = []
    abstained: list[str] = []
    observer_issues: list[dict] = []

    for agent, result in zip(active_agents, results):
        if isinstance(result, Exception):
            logger.error(
                "phase3_agent_error",
                extra={"agent_id": agent.id, "error": str(result)},
            )
            abstained.append(agent.id)
            continue

        raw_content, verdict, abstain_reason = result
        if verdict is None:
            abstained.append(agent.id)
            logger.warning(
                "phase3_agent_abstained",
                extra={"agent_id": agent.id, "reason": abstain_reason},
            )
            continue

        verdicts.append(verdict)

        # Observer verdict grounding check
        if observer is not None:
            import json
            obs_result = await observer.check(
                round_num=-1,
                check_type="verdict_grounding",
                subject_id=agent.id,
                graph=graph,
                subject_output=json.dumps(verdict.raw),
            )
            if obs_result.response:
                for issue in obs_result.response.issues:
                    observer_issues.append({"agent_id": agent.id, "issue": issue})

    if artifacts_writer:
        artifacts_writer.write_verdicts(verdicts)

    return Phase3Result(
        verdicts=verdicts,
        abstained_agents=abstained,
        observer_issues=observer_issues,
    )


async def _call_agent_phase3(
    agent: SubAgent,
    question: str,
    graph: ClaimGraph,
    known_ids: set[str],
) -> tuple[str, Optional[VerdictResponse], str]:
    graph_state = serialize_open_state(graph, agent.id)
    user_content = phase3_user(
        question=question,
        agent_id=agent.id,
        graph_state=graph_state,
        my_claim_ids=list(agent.claim_ids),
        my_falsifier_history=agent.falsifier_history,
    )
    messages = [{"role": "user", "content": user_content}]

    result = await agent.call(messages, round_num=-1, system=PHASE3_SYSTEM)
    if result.abstained:
        return ("", None, result.abstain_reason)

    raw_content = result.response.content

    try:
        verdict = parse_verdict(raw_content, agent.id, known_ids)
        return (raw_content, verdict, "")
    except (ParseError, SchemaError) as e:
        logger.warning(
            "phase3_parse_error_retrying",
            extra={"agent_id": agent.id, "error": str(e)},
        )
        retry = await agent.retry_with_reformat(
            original_messages=messages,
            original_response_content=raw_content,
            round_num=-1,
            system=PHASE3_SYSTEM,
        )
        if retry.abstained:
            return ("", None, "reformat_timeout")
        try:
            verdict = parse_verdict(retry.response.content, agent.id, known_ids)
            return (retry.response.content, verdict, "")
        except (ParseError, SchemaError) as e2:
            return (retry.response.content, None, f"parse_failed: {e2}")
