"""JSON extraction and schema validation for all LLM response types.

Used by council agents (phases 1–3), the arbiter, and the observer.
Raises ParseError for malformed JSON, SchemaError for missing/invalid fields.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ParseError(Exception):
    pass


class SchemaError(ParseError):
    pass


def _extract_json(text: str) -> str:
    """Try to extract a JSON object from text that may have surrounding prose."""
    text = text.strip()
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ParseError(f"No JSON object found in response (length {len(text)})")
    return text[start : end + 1]


def parse_json_response(content: str) -> dict:
    """Parse JSON from an LLM response, extracting from surrounding prose if needed."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        extracted = _extract_json(content)
        try:
            return json.loads(extracted)
        except json.JSONDecodeError as e:
            raise ParseError(f"Failed to parse JSON: {e}\nContent: {content[:200]}") from e


def _require(d: dict, key: str, context: str) -> Any:
    if key not in d:
        raise SchemaError(f"Missing required field '{key}' in {context}")
    return d[key]


# --------------------------------------------------------------------------
# Phase 1
# --------------------------------------------------------------------------

@dataclass
class Phase1Response:
    agent_id: str
    scratchpad: str
    new_claims: list[dict]
    new_evidence: list[dict]
    raw: dict = field(default_factory=dict)


def parse_phase1(content: str, expected_agent_id: str) -> Phase1Response:
    data = parse_json_response(content)
    agent_id = data.get("agent_id", expected_agent_id)

    claims = []
    for i, c in enumerate(data.get("new_claims", [])):
        if "text" not in c:
            raise SchemaError(f"new_claims[{i}] missing 'text'")
        if "type" not in c:
            raise SchemaError(f"new_claims[{i}] missing 'type'")
        valid_types = {"fact", "value", "policy", "causal"}
        if c["type"] not in valid_types:
            raise SchemaError(f"new_claims[{i}] invalid type '{c['type']}', must be one of {valid_types}")
        claims.append({
            "text": c["text"],
            "type": c["type"],
            "confidence": float(c.get("confidence", 1.0)),
            "falsifier": c.get("falsifier"),
        })

    evidence = []
    for i, e in enumerate(data.get("new_evidence", [])):
        if "text" not in e:
            raise SchemaError(f"new_evidence[{i}] missing 'text'")
        valid_types = {"empirical", "testimony", "statistical", "logical"}
        ev_type = e.get("type", "empirical")
        if ev_type not in valid_types:
            raise SchemaError(f"new_evidence[{i}] invalid type '{ev_type}'")
        evidence.append({
            "text": e["text"],
            "source": e.get("source", "unspecified"),
            "type": ev_type,
            "supports": e.get("supports"),
        })

    return Phase1Response(
        agent_id=agent_id,
        scratchpad=data.get("scratchpad", ""),
        new_claims=claims,
        new_evidence=evidence,
        raw=data,
    )


# --------------------------------------------------------------------------
# Phase 2
# --------------------------------------------------------------------------

@dataclass
class Phase2Response:
    agent_id: str
    round: int
    scratchpad: str
    new_claims: list[dict]
    new_evidence: list[dict]
    new_edges: list[dict]
    position_updates: list[dict]
    raw: dict = field(default_factory=dict)


_VALID_EDGE_TYPES = {"supports", "contradicts", "rebuts", "depends_on"}
_VALID_CLAIM_TYPES = {"fact", "value", "policy", "causal"}


def _resolve_node_id(raw_id: str, known_node_ids: set[str]) -> str:
    """Resolve a bare ID (e.g. 'abc123') to its prefixed form ('claim:abc123') if known."""
    if raw_id in known_node_ids:
        return raw_id
    for prefix in ("claim", "evidence", "assumption", "edge"):
        candidate = f"{prefix}:{raw_id}"
        if candidate in known_node_ids:
            return candidate
    return raw_id  # return as-is; downstream validation will reject if still unknown


def parse_phase2(
    content: str,
    expected_agent_id: str,
    round_num: int,
    known_node_ids: set[str],
    agent_claim_ids: set[str],
) -> Phase2Response:
    data = parse_json_response(content)
    agent_id = data.get("agent_id", expected_agent_id)

    claims = []
    for i, c in enumerate(data.get("new_claims", [])):
        if "text" not in c:
            raise SchemaError(f"new_claims[{i}] missing 'text'")
        ct = c.get("type", "fact")
        if ct not in _VALID_CLAIM_TYPES:
            raise SchemaError(f"new_claims[{i}] invalid type '{ct}'")
        claims.append({
            "text": c["text"],
            "type": ct,
            "confidence": float(c.get("confidence", 1.0)),
            "falsifier": c.get("falsifier"),
        })

    evidence = []
    for i, e in enumerate(data.get("new_evidence", [])):
        if "text" not in e:
            raise SchemaError(f"new_evidence[{i}] missing 'text'")
        evidence.append({
            "text": e["text"],
            "source": e.get("source", "unspecified"),
            "type": e.get("type", "empirical"),
            "supports": e.get("supports"),
        })

    edges = []
    for i, e in enumerate(data.get("new_edges", [])):
        etype = e.get("type")
        if etype not in _VALID_EDGE_TYPES:
            raise SchemaError(
                f"new_edges[{i}] invalid type '{etype}'. "
                f"Valid types: {_VALID_EDGE_TYPES}"
            )
        from_id = e.get("from")
        to_id = e.get("to")
        if not from_id or not to_id:
            raise SchemaError(f"new_edges[{i}] missing 'from' or 'to'")
        from_id = _resolve_node_id(from_id, known_node_ids)
        to_id = _resolve_node_id(to_id, known_node_ids)
        edges.append({
            "type": etype,
            "from": from_id,
            "to": to_id,
            "rationale": e.get("rationale", ""),
        })

    updates = []
    for i, u in enumerate(data.get("position_updates", [])):
        if "claim_id" not in u:
            raise SchemaError(f"position_updates[{i}] missing 'claim_id'")
        if "new_confidence" not in u:
            raise SchemaError(f"position_updates[{i}] missing 'new_confidence'")
        if "triggered_by" not in u or not u["triggered_by"]:
            raise SchemaError(
                f"position_updates[{i}] missing 'triggered_by' — "
                "position changes must cite specific triggering evidence"
            )
        if "reasoning" not in u or not u["reasoning"].strip():
            raise SchemaError(f"position_updates[{i}] missing 'reasoning'")

        claim_id = _resolve_node_id(u["claim_id"], known_node_ids)
        # Agents may only update their own claims
        if known_node_ids and claim_id not in agent_claim_ids:
            logger.warning(
                "rejected_foreign_update",
                extra={"agent": agent_id, "claim_id": claim_id},
            )
            continue  # Silently drop, logged above

        updates.append({
            "claim_id": claim_id,
            "new_confidence": float(u["new_confidence"]),
            "triggered_by": u["triggered_by"],
            "reasoning": u["reasoning"],
        })

    return Phase2Response(
        agent_id=agent_id,
        round=round_num,
        scratchpad=data.get("scratchpad", ""),
        new_claims=claims,
        new_evidence=evidence,
        new_edges=edges,
        position_updates=updates,
        raw=data,
    )


# --------------------------------------------------------------------------
# Arbiter
# --------------------------------------------------------------------------

@dataclass
class ArbiterResponse:
    scratchpad: str
    round: int
    merges: list[dict]
    status_changes: list[dict]
    targeted_query: str
    termination_signal: str
    termination_reasoning: str
    raw: dict = field(default_factory=dict)


def parse_arbiter(content: str, round_num: int) -> ArbiterResponse:
    data = parse_json_response(content)
    graph_ops = data.get("graph_operations", {})
    term_signal = data.get("termination_signal", "continue")
    if term_signal not in {"continue", "terminate", "abort"}:
        raise SchemaError(f"Invalid termination_signal '{term_signal}'")
    return ArbiterResponse(
        scratchpad=data.get("scratchpad", ""),
        round=round_num,
        merges=graph_ops.get("merges", []),
        status_changes=graph_ops.get("status_changes", []),
        targeted_query=data.get("targeted_query", ""),
        termination_signal=term_signal,
        termination_reasoning=data.get("termination_reasoning", ""),
        raw=data,
    )


# --------------------------------------------------------------------------
# Observer
# --------------------------------------------------------------------------

@dataclass
class ObserverResponse:
    round: int
    check_type: str
    subject_id: str
    passed: bool
    issues: list[dict]
    recommended_action: str
    raw: dict = field(default_factory=dict)


def parse_observer(content: str, round_num: int) -> ObserverResponse:
    data = parse_json_response(content)
    action = data.get("recommended_action", "continue")
    if action not in {"continue", "retry", "abort"}:
        raise SchemaError(f"Invalid recommended_action '{action}'")
    return ObserverResponse(
        round=round_num,
        check_type=data.get("check_type", "unknown"),
        subject_id=data.get("subject_id", "unknown"),
        passed=bool(data.get("passed", True)),
        issues=data.get("issues", []),
        recommended_action=action,
        raw=data,
    )


# --------------------------------------------------------------------------
# Phase 3 verdict
# --------------------------------------------------------------------------

@dataclass
class VerdictResponse:
    agent_id: str
    final_position: str
    original_claims_surviving: list[dict]
    original_claims_abandoned: list[dict]
    compelling_challenges_from_others: list[dict]
    rejected_challenges_from_others: list[dict]
    remaining_uncertainties: list[str]
    raw: dict = field(default_factory=dict)


def parse_verdict(
    content: str,
    expected_agent_id: str,
    known_node_ids: set[str],
) -> VerdictResponse:
    data = parse_json_response(content)
    agent_id = data.get("agent_id", expected_agent_id)

    # Validate claim_id references in all list fields
    for field_name in (
        "original_claims_surviving",
        "original_claims_abandoned",
        "compelling_challenges_from_others",
        "rejected_challenges_from_others",
    ):
        for i, item in enumerate(data.get(field_name, [])):
            if "claim_id" in item and known_node_ids and item["claim_id"] not in known_node_ids:
                logger.warning(
                    "verdict_unknown_claim_ref",
                    extra={"agent": agent_id, "field": field_name, "claim_id": item["claim_id"]},
                )

    return VerdictResponse(
        agent_id=agent_id,
        final_position=data.get("final_position", ""),
        original_claims_surviving=data.get("original_claims_surviving", []),
        original_claims_abandoned=data.get("original_claims_abandoned", []),
        compelling_challenges_from_others=data.get("compelling_challenges_from_others", []),
        rejected_challenges_from_others=data.get("rejected_challenges_from_others", []),
        remaining_uncertainties=data.get("remaining_uncertainties", []),
        raw=data,
    )
