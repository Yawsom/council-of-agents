from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum


class EdgeType(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    REBUTS = "rebuts"
    DEPENDS_ON = "depends_on"


# Valid source/target node-type prefixes per edge type.
# rebuts/contradicts must target a claim; supports/depends_on are more permissive.
_VALID_TARGETS: dict[EdgeType, set[str]] = {
    EdgeType.SUPPORTS: {"claim", "evidence", "assumption"},
    EdgeType.CONTRADICTS: {"claim"},
    EdgeType.REBUTS: {"claim"},
    EdgeType.DEPENDS_ON: {"claim", "assumption"},
}

_VALID_SOURCES: dict[EdgeType, set[str]] = {
    EdgeType.SUPPORTS: {"claim", "evidence"},
    EdgeType.CONTRADICTS: {"claim", "evidence"},
    EdgeType.REBUTS: {"claim"},
    EdgeType.DEPENDS_ON: {"claim"},
}


class EdgeValidationError(ValueError):
    pass


def _node_prefix(node_id: str) -> str:
    return node_id.split(":")[0] if ":" in node_id else "unknown"


def validate_edge(edge_type: EdgeType, from_id: str, to_id: str) -> None:
    if from_id == to_id:
        raise EdgeValidationError(
            f"Self-loop edge rejected: '{from_id}' cannot point to itself"
        )

    src_prefix = _node_prefix(from_id)
    tgt_prefix = _node_prefix(to_id)

    valid_src = _VALID_SOURCES.get(edge_type, set())
    valid_tgt = _VALID_TARGETS.get(edge_type, set())

    if src_prefix not in valid_src:
        raise EdgeValidationError(
            f"Edge type '{edge_type}' cannot have source node type '{src_prefix}'. "
            f"Valid source types: {valid_src}"
        )
    if tgt_prefix not in valid_tgt:
        raise EdgeValidationError(
            f"Edge type '{edge_type}' cannot have target node type '{tgt_prefix}'. "
            f"Valid target types: {valid_tgt}"
        )


@dataclass
class Edge:
    id: str
    type: EdgeType
    from_id: str
    to_id: str
    rationale: str
    proposer: str
    round_introduced: int

    @classmethod
    def create(
        cls,
        edge_type: EdgeType,
        from_id: str,
        to_id: str,
        rationale: str,
        proposer: str,
        round_introduced: int,
    ) -> "Edge":
        validate_edge(edge_type, from_id, to_id)
        edge_id = f"edge:{uuid.uuid4().hex[:8]}"
        return cls(
            id=edge_id,
            type=edge_type,
            from_id=from_id,
            to_id=to_id,
            rationale=rationale,
            proposer=proposer,
            round_introduced=round_introduced,
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "rationale": self.rationale,
            "proposer": self.proposer,
            "round_introduced": self.round_introduced,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Edge":
        return cls(
            id=d["id"],
            type=EdgeType(d["type"]),
            from_id=d["from_id"],
            to_id=d["to_id"],
            rationale=d.get("rationale", ""),
            proposer=d.get("proposer", "unknown"),
            round_introduced=d.get("round_introduced", 0),
        )
