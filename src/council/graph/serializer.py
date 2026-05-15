from __future__ import annotations

from .edges import EdgeType
from .graph import ClaimGraph
from .nodes import ClaimStatus


def serialize_open_state(graph: ClaimGraph, agent_id: str) -> str:
    """Serialize the open state of the claim graph to structured text for agent prompts."""
    lines: list[str] = []

    open_claims = graph.open_claims()
    contested_claims = graph.contested_claims()
    all_active = open_claims + contested_claims

    if not all_active:
        lines.append("## Current Claim Graph State\n\nNo active claims yet.\n")
        return "\n".join(lines)

    lines.append("## Current Claim Graph State\n")

    # --- Claims ---
    if all_active:
        lines.append("### Active Claims\n")
        for claim in all_active:
            agent_conf = claim.per_agent_confidence.get(agent_id, None)
            conf_str = f"{agent_conf:.2f}" if agent_conf is not None else "unknown"
            lines.append(
                f"[{claim.id}] ({claim.type.value}, status={claim.status.value}, "
                f"your_confidence={conf_str})"
            )
            lines.append(f"  Text: {claim.text}")
            if claim.falsifier:
                lines.append(f"  Falsifier: {claim.falsifier}")
            if claim.merged_phrasings:
                lines.append(f"  Also phrased as: {'; '.join(claim.merged_phrasings)}")

            # Edges attached to this claim
            related_edges = graph.edges_for_node(claim.id)
            if related_edges:
                for edge in related_edges:
                    lines.append(
                        f"    [{edge.id}] {edge.type.value}: {edge.from_id} → {edge.to_id}"
                        f"  (by {edge.proposer}: {edge.rationale})"
                    )
            lines.append("")

    # --- Evidence ---
    if graph.evidence:
        lines.append("### Evidence\n")
        for ev in graph.evidence:
            lines.append(f"[{ev.id}] ({ev.type.value}) by {ev.proposer}")
            lines.append(f"  Text: {ev.text}")
            lines.append(f"  Source: {ev.source}")
            lines.append("")

    # --- Assumptions ---
    active_assumptions = [a for a in graph.assumptions if not a.challenged]
    if active_assumptions:
        lines.append("### Unchallenged Assumptions\n")
        for assumption in active_assumptions:
            lines.append(f"[{assumption.id}] {assumption.text}")
            lines.append(f"  Underpins: {', '.join(assumption.held_by)}")
            lines.append("")

    # --- Unresolved cruxes: challenged claims with unanswered challenges ---
    unanswered = _find_unanswered_challenges(graph)
    if unanswered:
        lines.append("### Unanswered Challenges\n")
        for claim_id, challenge_ids in unanswered.items():
            claim = graph.get_node(claim_id)
            if claim:
                lines.append(f"Claim [{claim_id}]: {claim.text}")
                for cid in challenge_ids:
                    cedge = graph._edges.get(cid)
                    if cedge:
                        src = graph.get_node(cedge.from_id)
                        src_text = src.text if src else cedge.from_id
                        lines.append(f"  Challenge [{cid}]: {src_text}")
                lines.append("")

    return "\n".join(lines)


def _find_unanswered_challenges(graph: ClaimGraph) -> dict[str, list[str]]:
    """Return {claim_id: [challenge_edge_ids]} for challenges that have no rebuttal."""
    # A challenge is an edge of type contradicts/rebuts pointing at a claim.
    # It's "answered" if there's a supports or rebuts edge from the target claim or
    # its supporters back toward the challenger.
    challenge_edges = [
        e for e in graph.edges if e.type in (EdgeType.CONTRADICTS, EdgeType.REBUTS)
    ]
    rebuttal_edges = {e.to_id for e in graph.edges if e.type == EdgeType.REBUTS}

    result: dict[str, list[str]] = {}
    for edge in challenge_edges:
        # Check if there's any rebuttal edge targeting the challenging claim/source
        if edge.from_id not in rebuttal_edges:
            result.setdefault(edge.to_id, []).append(edge.id)
    return result
