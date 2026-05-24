"""Arbiter — provocateur that drives debate between rounds.

After each agent round the arbiter reviews the graph, issues a targeted query
for the next round, may apply graph operations (merges, status changes), and
can signal early termination or abort.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..agents.parser import ArbiterResponse, ParseError, SchemaError, parse_arbiter
from ..agents.prompts import ARBITER_SYSTEM, arbiter_user
from ..graph.graph import ClaimGraph
from ..graph.nodes import ClaimStatus
from ..graph.serializer import serialize_open_state
from ..providers.base import LLMProvider

logger = logging.getLogger(__name__)

ARBITER_AGENT_ID = "arbiter"


@dataclass
class ArbiterCallResult:
    response: Optional[ArbiterResponse]
    abstained: bool = False
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Arbiter:
    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        temperature: float = 0.2,
        seed: Optional[int] = None,
        timeout: float = 90.0,
    ) -> None:
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.seed = seed
        self.timeout = timeout
        self.cost_log: list[dict] = []

    async def run(
        self,
        question: str,
        round_num: int,
        graph: ClaimGraph,
        termination_stats: dict,
    ) -> ArbiterCallResult:
        graph_state = serialize_open_state(graph, ARBITER_AGENT_ID)
        unchallenged = self._find_unchallenged_claim_ids(graph)
        unanswered = self._find_unanswered_challenge_ids(graph)

        user_content = arbiter_user(
            question=question,
            round_num=round_num,
            graph_state=graph_state,
            unchallenged_claim_ids=unchallenged,
            unanswered_challenge_ids=unanswered,
            termination_stats=termination_stats,
        )
        messages = [
            {"role": "system", "content": ARBITER_SYSTEM},
            {"role": "user", "content": user_content},
        ]

        import asyncio
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
            logger.warning("arbiter_timeout", extra={"round": round_num})
            return ArbiterCallResult(response=None, abstained=True)
        except Exception as e:
            logger.warning("arbiter_error", extra={"round": round_num, "error": str(e)[:200]})
            return ArbiterCallResult(response=None, abstained=True)

        self.cost_log.append({
            "round": round_num,
            "prompt_tokens": llm_response.prompt_tokens,
            "completion_tokens": llm_response.completion_tokens,
            "cost_usd": llm_response.cost_usd,
        })

        try:
            parsed = parse_arbiter(llm_response.content, round_num)
        except (ParseError, SchemaError) as e:
            logger.warning("arbiter_parse_error", extra={"round": round_num, "error": str(e)})
            return ArbiterCallResult(response=None, abstained=True)

        return ArbiterCallResult(
            response=parsed,
            cost_usd=llm_response.cost_usd,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
        )

    def apply_graph_operations(
        self, response: ArbiterResponse, graph: ClaimGraph
    ) -> list[str]:
        """Apply validated graph operations. Returns list of warning messages."""
        warnings = []

        for merge_op in response.merges:
            ids = merge_op.get("claim_ids", [])
            if len(ids) < 2:
                warnings.append(f"Merge op has fewer than 2 claim IDs: {ids}")
                continue
            # Validate all IDs exist
            missing = [cid for cid in ids if not graph.node_exists(cid)]
            if missing:
                warnings.append(f"Merge op references unknown IDs: {missing}")
                continue
            # Merge all into first
            primary_id = ids[0]
            for secondary_id in ids[1:]:
                try:
                    graph.merge_claims(primary_id, secondary_id)
                    logger.info(
                        "arbiter_merge",
                        extra={
                            "primary": primary_id,
                            "secondary": secondary_id,
                            "rationale": merge_op.get("rationale", ""),
                        },
                    )
                except (KeyError, ValueError) as e:
                    warnings.append(f"Merge failed ({primary_id} ← {secondary_id}): {e}")

        valid_statuses = {s.value for s in ClaimStatus}
        for sc in response.status_changes:
            claim_id = sc.get("claim_id")
            new_status = sc.get("new_status")
            if not claim_id or not new_status:
                warnings.append(f"Status change missing claim_id or new_status: {sc}")
                continue
            if not graph.node_exists(claim_id):
                warnings.append(f"Status change references unknown claim: {claim_id}")
                continue
            if new_status not in valid_statuses:
                warnings.append(f"Invalid status '{new_status}' for claim {claim_id}")
                continue
            try:
                graph.update_claim_status(claim_id, ClaimStatus(new_status))
                logger.info(
                    "arbiter_status_change",
                    extra={"claim_id": claim_id, "new_status": new_status},
                )
            except Exception as e:
                warnings.append(f"Status change failed for {claim_id}: {e}")

        for w in warnings:
            logger.warning("arbiter_graph_op_warning", extra={"detail": w})

        return warnings

    def _find_unchallenged_claim_ids(self, graph: ClaimGraph) -> list[str]:
        from ..graph.edges import EdgeType
        challenged = {
            e.to_id for e in graph.edges
            if e.type in (EdgeType.CONTRADICTS, EdgeType.REBUTS)
        }
        return [
            c.id for c in graph.open_claims()
            if c.id not in challenged
        ]

    def _find_unanswered_challenge_ids(self, graph: ClaimGraph) -> list[str]:
        from ..graph.edges import EdgeType
        rebutted = {e.to_id for e in graph.edges if e.type == EdgeType.REBUTS}
        return [
            e.id for e in graph.edges
            if e.type in (EdgeType.CONTRADICTS, EdgeType.REBUTS) and e.from_id not in rebutted
        ]

    def total_cost(self) -> float:
        return sum(e["cost_usd"] for e in self.cost_log)
