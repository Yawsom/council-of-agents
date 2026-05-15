from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ClaimType(str, Enum):
    FACT = "fact"
    VALUE = "value"
    POLICY = "policy"
    CAUSAL = "causal"


class ClaimStatus(str, Enum):
    OPEN = "open"
    CONTESTED = "contested"
    SUPPORTED = "supported"
    REJECTED = "rejected"


class EvidenceType(str, Enum):
    EMPIRICAL = "empirical"
    TESTIMONY = "testimony"
    STATISTICAL = "statistical"
    LOGICAL = "logical"


@dataclass
class Claim:
    id: str
    text: str
    type: ClaimType
    proposer: str
    round_introduced: int
    status: ClaimStatus = ClaimStatus.OPEN
    per_agent_confidence: dict[str, Optional[float]] = field(default_factory=dict)
    falsifier: Optional[str] = None
    merged_phrasings: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        text: str,
        claim_type: ClaimType,
        proposer: str,
        round_introduced: int,
        confidence: float = 1.0,
        falsifier: Optional[str] = None,
    ) -> "Claim":
        node_id = f"claim:{uuid.uuid4().hex[:8]}"
        return cls(
            id=node_id,
            text=text,
            type=claim_type,
            proposer=proposer,
            round_introduced=round_introduced,
            status=ClaimStatus.OPEN,
            per_agent_confidence={proposer: confidence},
            falsifier=falsifier,
            merged_phrasings=[],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "type": self.type.value,
            "proposer": self.proposer,
            "round_introduced": self.round_introduced,
            "status": self.status.value,
            "per_agent_confidence": self.per_agent_confidence,
            "falsifier": self.falsifier,
            "merged_phrasings": self.merged_phrasings,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Claim":
        return cls(
            id=d["id"],
            text=d["text"],
            type=ClaimType(d["type"]),
            proposer=d["proposer"],
            round_introduced=d["round_introduced"],
            status=ClaimStatus(d["status"]),
            per_agent_confidence=d.get("per_agent_confidence", {}),
            falsifier=d.get("falsifier"),
            merged_phrasings=d.get("merged_phrasings", []),
        )


@dataclass
class Evidence:
    id: str
    text: str
    source: str
    type: EvidenceType
    proposer: str
    round_introduced: int
    per_agent_reliability: dict[str, Optional[float]] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        text: str,
        source: str,
        evidence_type: EvidenceType,
        proposer: str,
        round_introduced: int,
    ) -> "Evidence":
        node_id = f"evidence:{uuid.uuid4().hex[:8]}"
        return cls(
            id=node_id,
            text=text,
            source=source,
            type=evidence_type,
            proposer=proposer,
            round_introduced=round_introduced,
            per_agent_reliability={proposer: 1.0},
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "source": self.source,
            "type": self.type.value,
            "proposer": self.proposer,
            "round_introduced": self.round_introduced,
            "per_agent_reliability": self.per_agent_reliability,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Evidence":
        return cls(
            id=d["id"],
            text=d["text"],
            source=d["source"],
            type=EvidenceType(d["type"]),
            proposer=d["proposer"],
            round_introduced=d["round_introduced"],
            per_agent_reliability=d.get("per_agent_reliability", {}),
        )


@dataclass
class Assumption:
    id: str
    text: str
    held_by: list[str]  # list of claim ids
    challenged: bool = False

    @classmethod
    def create(cls, text: str, held_by: list[str]) -> "Assumption":
        node_id = f"assumption:{uuid.uuid4().hex[:8]}"
        return cls(id=node_id, text=text, held_by=list(held_by), challenged=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "held_by": self.held_by,
            "challenged": self.challenged,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Assumption":
        return cls(
            id=d["id"],
            text=d["text"],
            held_by=d.get("held_by", []),
            challenged=d.get("challenged", False),
        )
