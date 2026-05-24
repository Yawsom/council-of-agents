"""Phase 1: sealed exploration.

Each council agent analyzes the question independently. Outputs are parsed,
deduplicated via identity.check_identity(), and ingested into the claim graph.
Agents that fail to produce valid JSON are marked excluded for later phases.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from ..agents.agent import SubAgent
from ..agents.parser import ParseError, SchemaError, parse_phase1
from ..agents.prompts import PHASE1_SYSTEM, phase1_user
from ..graph.graph import ClaimGraph
from ..graph.nodes import Claim, ClaimType, Evidence, EvidenceType
from ..identity.deduplicator import check_identity
from ..identity.embedder import Embedder
from ..providers.base import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class Phase1Result:
    graph: ClaimGraph
    agent_responses: list[dict]
    merge_log: list[dict] = field(default_factory=list)
    abstained_agents: list[str] = field(default_factory=list)


async def run_phase1(
    question: str,
    agents: list[SubAgent],
    graph: ClaimGraph,
    embedder: Embedder,
    llm_provider: LLMProvider,
    disambiguation_model: str,
    identity_cfg,
    artifacts_writer=None,
    stagger_delay: float = 0.0,
) -> Phase1Result:
    """Run sealed exploration: parallel agent calls, dedup, graph ingestion."""
    merge_log: list[dict] = []
    agent_responses: list[dict] = []
    abstained: list[str] = []

    # Staggered parallel calls — no agent sees another's output
    results = await _stagger_gather(
        [_call_agent_phase1(agent, question) for agent in agents],
        stagger_delay,
    )

    for agent, result in zip(agents, results):
        if isinstance(result, Exception):
            logger.error(
                "phase1_agent_error",
                extra={"agent_id": agent.id, "error": str(result)},
            )
            agent.excluded = True
            abstained.append(agent.id)
            continue

        raw_content, parsed, abstain_reason = result
        if parsed is None:
            agent.excluded = True
            abstained.append(agent.id)
            logger.warning(
                "phase1_agent_abstained",
                extra={"agent_id": agent.id, "reason": abstain_reason},
            )
            continue

        # Ingest claims into graph with deduplication
        for claim_data in parsed.new_claims:
            existing = graph.claims
            dedup = await check_identity(
                new_text=claim_data["text"],
                existing_claims=existing,
                embedder=embedder,
                llm=llm_provider,
                disambiguation_model=disambiguation_model,
                similarity_high=identity_cfg.similarity_high,
                similarity_low=identity_cfg.similarity_low,
                merge_log=merge_log,
            )

            if dedup.is_duplicate and dedup.merge_into:
                # Update proposer's confidence on the existing merged claim
                graph.update_agent_confidence(
                    dedup.merge_into, agent.id, claim_data["confidence"]
                )
                existing_claim = graph.get_node(dedup.merge_into)
                if existing_claim and claim_data["text"] not in existing_claim.merged_phrasings:
                    existing_claim.merged_phrasings.append(claim_data["text"])
                agent.claim_ids.add(dedup.merge_into)
            else:
                claim = Claim.create(
                    text=claim_data["text"],
                    claim_type=ClaimType(claim_data["type"]),
                    proposer=agent.id,
                    round_introduced=0,
                    confidence=claim_data["confidence"],
                    falsifier=claim_data.get("falsifier"),
                )
                graph.add_claim(claim)
                agent.claim_ids.add(claim.id)
                if claim_data.get("falsifier"):
                    agent.falsifier_history.append(claim_data["falsifier"])

        # Ingest evidence
        for ev_data in parsed.new_evidence:
            ev = Evidence.create(
                text=ev_data["text"],
                source=ev_data["source"],
                evidence_type=EvidenceType(ev_data["type"]),
                proposer=agent.id,
                round_introduced=0,
            )
            graph.add_evidence(ev)

        agent_responses.append({
            "agent_id": agent.id,
            "model": agent.model,
            "raw_content": raw_content,
            "parsed": parsed.raw,
        })

        stats = graph.stats()
        if stats["total_claims"] > 500:
            logger.warning(
                "graph_size_warning",
                extra={"total_claims": stats["total_claims"], "detail": "Graph > 500 claims — potential bug"},
            )

    if artifacts_writer:
        artifacts_writer.write_phase1_transcripts(agent_responses)
        artifacts_writer.write_graph_snapshot(graph, "phase1")
        artifacts_writer.write_merge_log(merge_log)

    return Phase1Result(
        graph=graph,
        agent_responses=agent_responses,
        merge_log=merge_log,
        abstained_agents=abstained,
    )


async def _stagger_gather(coroutines: list, stagger_delay: float) -> list:
    tasks = []
    for i, coro in enumerate(coroutines):
        if i > 0 and stagger_delay > 0:
            await asyncio.sleep(stagger_delay)
        tasks.append(asyncio.create_task(coro))
    return list(await asyncio.gather(*tasks, return_exceptions=True))


async def _call_agent_phase1(
    agent: SubAgent, question: str
) -> tuple[str, object, str]:
    """Returns (raw_content, parsed_response_or_None, abstain_reason)."""
    user_msg = phase1_user(question, agent.id)
    messages = [{"role": "user", "content": user_msg}]

    result = await agent.call(messages, round_num=0, system=PHASE1_SYSTEM)
    if result.abstained:
        return ("", None, result.abstain_reason)

    raw_content = result.response.content

    # Try parsing; on failure retry once with reformat
    try:
        parsed = parse_phase1(raw_content, agent.id)
        return (raw_content, parsed, "")
    except (ParseError, SchemaError) as e:
        logger.warning(
            "phase1_parse_error_retrying",
            extra={"agent_id": agent.id, "error": str(e)},
        )
        retry_result = await agent.retry_with_reformat(
            original_messages=messages,
            original_response_content=raw_content,
            round_num=0,
            system=PHASE1_SYSTEM,
        )
        if retry_result.abstained:
            return ("", None, "reformat_timeout")
        try:
            parsed = parse_phase1(retry_result.response.content, agent.id)
            return (retry_result.response.content, parsed, "")
        except (ParseError, SchemaError) as e2:
            logger.warning(
                "phase1_parse_error_abstaining",
                extra={"agent_id": agent.id, "error": str(e2)},
            )
            return (retry_result.response.content, None, f"parse_failed: {e2}")
