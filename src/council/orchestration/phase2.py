from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from ..agents.agent import SubAgent
from ..agents.parser import ParseError, Phase2Response, SchemaError, parse_phase2
from ..agents.prompts import build_phase2_system, phase2_user
from ..arbiter.arbiter import Arbiter
from ..graph.edges import Edge, EdgeType, EdgeValidationError
from ..graph.graph import ClaimGraph
from ..graph.nodes import Claim, ClaimType, Evidence, EvidenceType
from ..graph.serializer import serialize_open_state
from ..identity.deduplicator import check_identity
from ..identity.embedder import Embedder
from ..observer.observer import Observer
from ..providers.base import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class TerminationResult:
    reason: str  # "max_rounds" | "no_new_claims" | "no_challenges" | "low_update_rate" | "observer_abort" | "all_abstained" | "arbiter_terminate" | "arbiter_abort"
    round: int
    stats: dict = field(default_factory=dict)


@dataclass
class Phase2Result:
    graph: ClaimGraph
    termination: TerminationResult
    round_transcripts: list[dict] = field(default_factory=list)
    merge_log: list[dict] = field(default_factory=list)
    observer_log: list[dict] = field(default_factory=list)
    targeted_query: str = ""


async def _stagger_gather(coroutines: list, stagger_delay: float) -> list:
    tasks = []
    for i, coro in enumerate(coroutines):
        if i > 0 and stagger_delay > 0:
            await asyncio.sleep(stagger_delay)
        tasks.append(asyncio.create_task(coro))
    return list(await asyncio.gather(*tasks, return_exceptions=True))


async def run_phase2(
    question: str,
    agents: list[SubAgent],
    graph: ClaimGraph,
    arbiter: Arbiter,
    observer: Observer,
    embedder: Embedder,
    llm_provider: LLMProvider,
    termination_cfg,
    identity_cfg,
    observer_frequency: int,
    disambiguation_model: str,
    version: str = "A",
    disguise_pipeline=None,
    artifacts_writer=None,
    stagger_delay: float = 0.0,
) -> Phase2Result:
    merge_log: list[dict] = []
    round_transcripts: list[dict] = []
    observer_log: list[dict] = []
    targeted_query = "Begin stress-testing each other's initial claims. Identify the weakest assumptions and challenge them directly."

    # Termination tracking
    no_challenge_rounds = 0
    round_num = 1

    while True:
        logger.info("phase2_round_start", extra={"round": round_num})

        active_agents = [a for a in agents if not a.excluded]
        if not active_agents:
            logger.error("phase2_no_active_agents", extra={"round": round_num})
            return Phase2Result(
                graph=graph,
                termination=TerminationResult(
                    reason="all_abstained", round=round_num,
                    stats={"round": round_num},
                ),
                round_transcripts=round_transcripts,
                merge_log=merge_log,
                observer_log=observer_log,
                targeted_query=targeted_query,
            )

        # Staggered parallel agent calls (excluded agents already filtered above)
        agent_results = await _stagger_gather(
            [
                _call_agent_phase2(
                    agent=agent,
                    question=question,
                    round_num=round_num,
                    graph=graph,
                    targeted_query=targeted_query,
                    version=version,
                    disguise_pipeline=disguise_pipeline,
                )
                for agent in active_agents
            ],
            stagger_delay,
        )

        round_data: dict = {"round": round_num, "agents": [], "arbiter": None, "observer": []}
        new_claims_this_round = 0
        new_challenges_this_round = 0
        position_updates_this_round = 0
        all_abstained = True

        for agent, result in zip(active_agents, agent_results):
            if isinstance(result, Exception):
                logger.error(
                    "phase2_agent_error",
                    extra={"agent_id": agent.id, "round": round_num, "error": str(result)},
                )
                agent.excluded = True
                continue

            raw_content, parsed, abstain_reason = result
            agent_entry = {
                "agent_id": agent.id,
                "model": agent.model,
                "abstained": parsed is None,
                "abstain_reason": abstain_reason,
                "raw_content": raw_content,
                "parsed": parsed.raw if parsed else None,
            }
            round_data["agents"].append(agent_entry)

            if parsed is None:
                agent.excluded = True
                continue
            all_abstained = False

            # --- Ingest new claims ---
            for claim_data in parsed.new_claims:
                dedup = await check_identity(
                    new_text=claim_data["text"],
                    existing_claims=graph.claims,
                    embedder=embedder,
                    llm=llm_provider,
                    disambiguation_model=disambiguation_model,
                    similarity_high=identity_cfg.similarity_high,
                    similarity_low=identity_cfg.similarity_low,
                    merge_log=merge_log,
                )
                if dedup.is_duplicate and dedup.merge_into:
                    graph.update_agent_confidence(dedup.merge_into, agent.id, claim_data["confidence"])
                    existing_claim = graph.get_node(dedup.merge_into)
                    if existing_claim and claim_data["text"] not in existing_claim.merged_phrasings:
                        existing_claim.merged_phrasings.append(claim_data["text"])
                    agent.claim_ids.add(dedup.merge_into)
                else:
                    claim = Claim.create(
                        text=claim_data["text"],
                        claim_type=ClaimType(claim_data["type"]),
                        proposer=agent.id,
                        round_introduced=round_num,
                        confidence=claim_data["confidence"],
                        falsifier=claim_data.get("falsifier"),
                    )
                    graph.add_claim(claim)
                    agent.claim_ids.add(claim.id)
                    new_claims_this_round += 1
                    if claim_data.get("falsifier"):
                        agent.falsifier_history.append(claim_data["falsifier"])

            # --- Ingest new evidence ---
            for ev_data in parsed.new_evidence:
                ev = Evidence.create(
                    text=ev_data["text"],
                    source=ev_data["source"],
                    evidence_type=EvidenceType(ev_data.get("type", "empirical")),
                    proposer=agent.id,
                    round_introduced=round_num,
                )
                graph.add_evidence(ev)

            # --- Ingest new edges ---
            for edge_data in parsed.new_edges:
                from_id = edge_data["from"]
                to_id = edge_data["to"]
                # Remap any text-based IDs to actual graph IDs if needed
                from_node = graph.get_node(from_id)
                to_node = graph.get_node(to_id)
                if from_node is None or to_node is None:
                    logger.warning(
                        "phase2_edge_unknown_node",
                        extra={
                            "agent": agent.id,
                            "from_id": from_id,
                            "to_id": to_id,
                            "round": round_num,
                        },
                    )
                    continue
                try:
                    edge = Edge.create(
                        edge_type=EdgeType(edge_data["type"]),
                        from_id=from_id,
                        to_id=to_id,
                        rationale=edge_data.get("rationale", ""),
                        proposer=agent.id,
                        round_introduced=round_num,
                    )
                    graph.add_edge(edge)
                    if edge.type in (EdgeType.CONTRADICTS, EdgeType.REBUTS):
                        new_challenges_this_round += 1
                except EdgeValidationError as e:
                    logger.warning(
                        "phase2_edge_rejected",
                        extra={"agent": agent.id, "error": str(e), "round": round_num},
                    )

            # --- Apply position updates ---
            for update in parsed.position_updates:
                claim_id = update["claim_id"]
                if not graph.node_exists(claim_id):
                    logger.warning(
                        "phase2_position_update_unknown_claim",
                        extra={"agent": agent.id, "claim_id": claim_id},
                    )
                    continue
                if claim_id not in agent.claim_ids:
                    logger.warning(
                        "phase2_rejected_foreign_update",
                        extra={"agent": agent.id, "claim_id": claim_id},
                    )
                    continue
                graph.update_agent_confidence(claim_id, agent.id, update["new_confidence"])
                position_updates_this_round += 1

        if all_abstained:
            logger.error("phase2_all_agents_abstained", extra={"round": round_num})
            return Phase2Result(
                graph=graph,
                termination=TerminationResult(
                    reason="all_abstained", round=round_num,
                    stats={"round": round_num},
                ),
                round_transcripts=round_transcripts,
                merge_log=merge_log,
                observer_log=observer_log,
                targeted_query=targeted_query,
            )

        # --- Arbiter ---
        n_agents = len(agents)
        update_rate = position_updates_this_round / max(1, n_agents)
        termination_stats = {
            "round": round_num,
            "new_claims_this_round": new_claims_this_round,
            "new_challenges_this_round": new_challenges_this_round,
            "position_update_rate": update_rate,
            "no_challenge_rounds": no_challenge_rounds,
        }
        arbiter_result = await arbiter.run(question, round_num, graph, termination_stats)

        if not arbiter_result.abstained and arbiter_result.response:
            arb = arbiter_result.response
            warnings = arbiter.apply_graph_operations(arb, graph)
            targeted_query = arb.targeted_query
            round_data["arbiter"] = {
                "scratchpad": arb.scratchpad,
                "targeted_query": arb.targeted_query,
                "graph_operations": {"merges": arb.merges, "status_changes": arb.status_changes},
                "termination_signal": arb.termination_signal,
                "termination_reasoning": arb.termination_reasoning,
                "warnings": warnings,
            }

            if arb.termination_signal in ("terminate", "abort"):
                round_transcripts.append(round_data)
                if artifacts_writer:
                    artifacts_writer.write_round_snapshot(graph, round_num)
                    artifacts_writer.write_round_transcripts(round_data)
                return Phase2Result(
                    graph=graph,
                    termination=TerminationResult(
                        reason=f"arbiter_{arb.termination_signal}",
                        round=round_num,
                        stats=termination_stats,
                    ),
                    round_transcripts=round_transcripts,
                    merge_log=merge_log,
                    observer_log=observer_log,
                    targeted_query=targeted_query,
                )

        # --- Observer ---
        if observer_frequency > 0 and round_num % observer_frequency == 0:
            for agent, agent_entry in zip(active_agents, round_data["agents"]):
                if agent_entry["parsed"] is None:
                    continue
                obs_result = await observer.check(
                    round_num=round_num,
                    check_type="agent_faithfulness",
                    subject_id=agent.id,
                    graph=graph,
                    subject_output=json.dumps(agent_entry["parsed"]),
                )
                if obs_result.response:
                    observer_log.append(obs_result.response.raw)
                    round_data["observer"].append(obs_result.response.raw)
                if observer.should_abort(obs_result):
                    logger.error(
                        "observer_abort",
                        extra={"round": round_num, "agent": agent.id},
                    )
                    round_transcripts.append(round_data)
                    if artifacts_writer:
                        artifacts_writer.write_round_snapshot(graph, round_num)
                        artifacts_writer.write_round_transcripts(round_data)
                    return Phase2Result(
                        graph=graph,
                        termination=TerminationResult(
                            reason="observer_abort", round=round_num,
                            stats=termination_stats,
                        ),
                        round_transcripts=round_transcripts,
                        merge_log=merge_log,
                        observer_log=observer_log,
                        targeted_query=targeted_query,
                    )

        # --- Write artifacts ---
        round_transcripts.append(round_data)
        if artifacts_writer:
            artifacts_writer.write_round_snapshot(graph, round_num)
            artifacts_writer.write_round_transcripts(round_data)
            if merge_log:
                artifacts_writer.write_merge_log(merge_log)

        # --- Check termination ---
        if new_challenges_this_round == 0:
            no_challenge_rounds += 1
        else:
            no_challenge_rounds = 0

        term = _check_termination(
            round_num=round_num,
            new_claims=new_claims_this_round,
            update_rate=update_rate,
            no_challenge_rounds=no_challenge_rounds,
            cfg=termination_cfg,
        )
        if term:
            return Phase2Result(
                graph=graph,
                termination=TerminationResult(
                    reason=term, round=round_num, stats=termination_stats
                ),
                round_transcripts=round_transcripts,
                merge_log=merge_log,
                observer_log=observer_log,
                targeted_query=targeted_query,
            )

        stats = graph.stats()
        if stats["total_claims"] > 500:
            logger.warning(
                "graph_size_warning",
                extra={"total_claims": stats["total_claims"]},
            )

        round_num += 1


def _check_termination(
    round_num: int,
    new_claims: int,
    update_rate: float,
    no_challenge_rounds: int,
    cfg,
) -> Optional[str]:
    if round_num >= cfg.max_rounds:
        return "max_rounds"
    if new_claims < cfg.min_new_claims_per_round:
        return "no_new_claims"
    if no_challenge_rounds >= cfg.no_challenge_rounds:
        return "no_challenges"
    if update_rate < cfg.min_position_update_rate and round_num > 1:
        return "low_update_rate"
    return None


async def _call_agent_phase2(
    agent: SubAgent,
    question: str,
    round_num: int,
    graph: ClaimGraph,
    targeted_query: str,
    version: str,
    disguise_pipeline=None,
) -> tuple[str, Optional[Phase2Response], str]:
    # In Version B, inject synthetic peers into agent's view of graph state
    if version == "B" and disguise_pipeline is not None:
        graph_state = disguise_pipeline.inject_for_agent(agent.id, graph, round_num)
    else:
        graph_state = serialize_open_state(graph, agent.id)

    system = build_phase2_system(round_num)
    user_content = phase2_user(
        question=question,
        agent_id=agent.id,
        round_num=round_num,
        graph_state=graph_state,
        targeted_query=targeted_query,
        my_falsifiers=agent.falsifier_history,
    )
    messages = [{"role": "user", "content": user_content}]

    result = await agent.call(messages, round_num=round_num, system=system)
    if result.abstained:
        return ("", None, result.abstain_reason)

    raw_content = result.response.content
    known_ids = {n.id for n in graph.claims + graph.evidence + graph.assumptions}

    try:
        parsed = parse_phase2(
            content=raw_content,
            expected_agent_id=agent.id,
            round_num=round_num,
            known_node_ids=known_ids,
            agent_claim_ids=agent.claim_ids,
        )
        return (raw_content, parsed, "")
    except (ParseError, SchemaError) as e:
        logger.warning(
            "phase2_parse_error_retrying",
            extra={"agent_id": agent.id, "round": round_num, "error": str(e)},
        )
        retry = await agent.retry_with_reformat(
            original_messages=messages,
            original_response_content=raw_content,
            round_num=round_num,
            system=system,
        )
        if retry.abstained:
            return ("", None, "reformat_timeout")
        try:
            parsed = parse_phase2(
                content=retry.response.content,
                expected_agent_id=agent.id,
                round_num=round_num,
                known_node_ids=known_ids,
                agent_claim_ids=agent.claim_ids,
            )
            return (retry.response.content, parsed, "")
        except (ParseError, SchemaError) as e2:
            return (retry.response.content, None, f"parse_failed: {e2}")
