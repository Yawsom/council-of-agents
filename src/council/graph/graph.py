"""Claim graph — central shared state for a deliberation run.

All agents propose updates; orchestration ingests them into this graph.
The arbiter and observer read from it; serializer.py formats it for prompts.
"""
from __future__ import annotations

from typing import Optional, Union

from .edges import Edge, EdgeType, EdgeValidationError, validate_edge
from .nodes import Assumption, Claim, ClaimStatus, ClaimType, Evidence, EvidenceType

AnyNode = Union[Claim, Evidence, Assumption]


class ClaimGraph:
    """In-memory claim graph — the shared deliberation state."""

    def __init__(self) -> None:
        self._claims: dict[str, Claim] = {}
        self._evidence: dict[str, Evidence] = {}
        self._assumptions: dict[str, Assumption] = {}
        self._edges: dict[str, Edge] = {}

    # ------------------------------------------------------------------
    # Node accessors
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Optional[AnyNode]:
        if node_id in self._claims:
            return self._claims[node_id]
        if node_id in self._evidence:
            return self._evidence[node_id]
        if node_id in self._assumptions:
            return self._assumptions[node_id]
        return None

    def node_exists(self, node_id: str) -> bool:
        return self.get_node(node_id) is not None

    @property
    def claims(self) -> list[Claim]:
        return list(self._claims.values())

    @property
    def evidence(self) -> list[Evidence]:
        return list(self._evidence.values())

    @property
    def assumptions(self) -> list[Assumption]:
        return list(self._assumptions.values())

    @property
    def edges(self) -> list[Edge]:
        return list(self._edges.values())

    def open_claims(self) -> list[Claim]:
        return [c for c in self._claims.values() if c.status == ClaimStatus.OPEN]

    def contested_claims(self) -> list[Claim]:
        return [c for c in self._claims.values() if c.status == ClaimStatus.CONTESTED]

    def edges_for_node(self, node_id: str) -> list[Edge]:
        return [e for e in self._edges.values() if e.from_id == node_id or e.to_id == node_id]

    # ------------------------------------------------------------------
    # Node mutations
    # ------------------------------------------------------------------

    def add_claim(self, claim: Claim) -> Claim:
        self._claims[claim.id] = claim
        return claim

    def add_evidence(self, ev: Evidence) -> Evidence:
        self._evidence[ev.id] = ev
        return ev

    def add_assumption(self, assumption: Assumption) -> Assumption:
        self._assumptions[assumption.id] = assumption
        return assumption

    def add_edge(self, edge: Edge) -> Edge:
        self._edges[edge.id] = edge
        # If this edge is a challenge (contradicts/rebuts) to a claim, mark it contested
        if edge.type in (EdgeType.CONTRADICTS, EdgeType.REBUTS):
            target = self._claims.get(edge.to_id)
            if target and target.status == ClaimStatus.OPEN:
                target.status = ClaimStatus.CONTESTED
        return edge

    def update_claim_status(self, claim_id: str, new_status: ClaimStatus) -> None:
        claim = self._claims.get(claim_id)
        if claim is None:
            raise KeyError(f"Claim not found: {claim_id}")
        claim.status = new_status

    def update_agent_confidence(
        self, claim_id: str, agent_id: str, confidence: float
    ) -> None:
        claim = self._claims.get(claim_id)
        if claim is None:
            raise KeyError(f"Claim not found: {claim_id}")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence must be 0–1, got {confidence}")
        claim.per_agent_confidence[agent_id] = confidence

    # ------------------------------------------------------------------
    # Merge claims
    # ------------------------------------------------------------------

    def merge_claims(self, primary_id: str, secondary_id: str) -> Claim:
        """Merge secondary into primary. Preserves both phrasings. Returns merged claim."""
        primary = self._claims.get(primary_id)
        secondary = self._claims.get(secondary_id)
        if primary is None:
            raise KeyError(f"Primary claim not found: {primary_id}")
        if secondary is None:
            raise KeyError(f"Secondary claim not found: {secondary_id}")

        # Preserve both phrasings
        if primary.text not in primary.merged_phrasings:
            primary.merged_phrasings.append(primary.text)
        if secondary.text not in primary.merged_phrasings:
            primary.merged_phrasings.append(secondary.text)

        # Merge confidence maps (primary wins on conflict)
        for agent_id, conf in secondary.per_agent_confidence.items():
            if agent_id not in primary.per_agent_confidence:
                primary.per_agent_confidence[agent_id] = conf

        # Repoint edges from secondary → primary
        for edge in self._edges.values():
            if edge.from_id == secondary_id:
                edge.from_id = primary_id
            if edge.to_id == secondary_id:
                edge.to_id = primary_id

        # Remove secondary
        del self._claims[secondary_id]
        return primary

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "claims": [c.to_dict() for c in self._claims.values()],
            "evidence": [e.to_dict() for e in self._evidence.values()],
            "assumptions": [a.to_dict() for a in self._assumptions.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ClaimGraph":
        graph = cls()
        for c in d.get("claims", []):
            graph._claims[c["id"]] = Claim.from_dict(c)
        for e in d.get("evidence", []):
            graph._evidence[e["id"]] = Evidence.from_dict(e)
        for a in d.get("assumptions", []):
            graph._assumptions[a["id"]] = Assumption.from_dict(a)
        for e in d.get("edges", []):
            graph._edges[e["id"]] = Edge.from_dict(e)
        return graph

    def stats(self) -> dict:
        return {
            "total_claims": len(self._claims),
            "open_claims": len(self.open_claims()),
            "contested_claims": len(self.contested_claims()),
            "total_evidence": len(self._evidence),
            "total_assumptions": len(self._assumptions),
            "total_edges": len(self._edges),
        }
