from __future__ import annotations

import json
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..agents.parser import VerdictResponse
from ..graph.graph import ClaimGraph


class ArtifactsWriter:
    def __init__(self, base_dir: str, run_name: str) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = Path(base_dir) / f"{ts}_{run_name}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "transcripts" / "phase1").mkdir(parents=True, exist_ok=True)
        (self.run_dir / "graph_snapshots").mkdir(parents=True, exist_ok=True)

    def write_config_snapshot(self, config_yaml_str: str) -> None:
        (self.run_dir / "config.yaml").write_text(config_yaml_str)

    def write_phase1_transcripts(self, agent_responses: list[dict]) -> None:
        d = self.run_dir / "transcripts" / "phase1"
        d.mkdir(parents=True, exist_ok=True)
        for entry in agent_responses:
            agent_id = entry["agent_id"].replace("/", "_")
            (d / f"{agent_id}_output.json").write_text(
                json.dumps(entry.get("parsed", {}), indent=2)
            )
            if entry.get("raw_content"):
                (d / f"{agent_id}_raw.txt").write_text(entry["raw_content"])

    def write_round_transcripts(self, round_data: dict) -> None:
        r = round_data["round"]
        d = self.run_dir / "transcripts" / f"round_{r}"
        d.mkdir(parents=True, exist_ok=True)
        for entry in round_data.get("agents", []):
            agent_id = entry["agent_id"].replace("/", "_")
            (d / f"{agent_id}_output.json").write_text(
                json.dumps(entry.get("parsed", {}), indent=2)
            )
            if entry.get("raw_content"):
                (d / f"{agent_id}_raw.txt").write_text(entry["raw_content"])
        if round_data.get("arbiter"):
            (d / "arbiter_output.json").write_text(
                json.dumps(round_data["arbiter"], indent=2)
            )
        if round_data.get("observer"):
            (d / "observer_checks.json").write_text(
                json.dumps(round_data["observer"], indent=2)
            )

    def write_graph_snapshot(self, graph: ClaimGraph, label: str) -> None:
        path = self.run_dir / "graph_snapshots" / f"{label}.json"
        path.write_text(json.dumps(graph.to_dict(), indent=2))

    def write_round_snapshot(self, graph: ClaimGraph, round_num: int) -> None:
        self.write_graph_snapshot(graph, f"round_{round_num}")

    def write_final_graph(self, graph: ClaimGraph) -> None:
        (self.run_dir / "final_graph.json").write_text(
            json.dumps(graph.to_dict(), indent=2)
        )

    def write_verdicts(self, verdicts: list[VerdictResponse]) -> None:
        data = [v.raw for v in verdicts]
        (self.run_dir / "verdicts.json").write_text(json.dumps(data, indent=2))

    def write_merge_log(self, merge_log: list[dict]) -> None:
        path = self.run_dir / "merge_log.json"
        with open(path, "w") as f:
            for entry in merge_log:
                f.write(json.dumps(entry) + "\n")

    def write_observer_log(self, observer_log: list[dict]) -> None:
        path = self.run_dir / "observer_log.json"
        with open(path, "w") as f:
            for entry in observer_log:
                f.write(json.dumps(entry) + "\n")

    def write_manipulation_log(self, manipulation_log: list[dict]) -> None:
        path = self.run_dir / "manipulation_log.json"
        with open(path, "w") as f:
            for entry in manipulation_log:
                f.write(json.dumps(entry) + "\n")

    def write_cost_summary(
        self,
        agents_cost_logs: list[dict],
        arbiter_cost_log: list[dict],
        observer_cost_log: list[dict],
    ) -> None:
        summary = {
            "agents": agents_cost_logs,
            "arbiter": arbiter_cost_log,
            "observer": observer_cost_log,
            "totals": {
                "agents_usd": sum(e["cost_usd"] for a in agents_cost_logs for e in a.get("log", [])),
                "arbiter_usd": sum(e["cost_usd"] for e in arbiter_cost_log),
                "observer_usd": sum(e["cost_usd"] for e in observer_cost_log),
            },
        }
        summary["totals"]["total_usd"] = sum(summary["totals"].values())
        (self.run_dir / "cost_summary.json").write_text(json.dumps(summary, indent=2))

    def write_output_md(
        self,
        question: str,
        graph: ClaimGraph,
        verdicts: list[VerdictResponse],
        termination_reason: str,
        termination_round: int,
        abstained_agents: Optional[dict] = None,
    ) -> None:
        lines: list[str] = []
        lines.append("# Council of Agents — Results\n")
        lines.append(f"**Question:** {question}\n")
        lines.append(
            f"**Stress-test completed:** Round {termination_round} "
            f"(reason: {termination_reason})\n"
        )

        # --- Agent participation summary ---
        if abstained_agents:
            lines.append("**Agent participation:**\n")
            for agent_id, phases in abstained_agents.items():
                phase_str = ", ".join(phases)
                lines.append(f"- `{agent_id}` abstained in: {phase_str}")
            lines.append("")

        # --- Claim landscape ---
        lines.append("## Claim Landscape\n")
        lines.append(f"Total claims: {len(graph.claims)}, Evidence: {len(graph.evidence)}\n")

        all_claims = graph.claims
        if all_claims:
            lines.append("### All Claims\n")
            for claim in sorted(all_claims, key=lambda c: c.round_introduced):
                conf_summary = ", ".join(
                    f"{aid}={v:.2f}" for aid, v in claim.per_agent_confidence.items() if v is not None
                )
                lines.append(
                    f"**[{claim.id}]** `{claim.status.value}` `{claim.type.value}`  "
                    f"*(introduced round {claim.round_introduced} by {claim.proposer})*"
                )
                lines.append(f"> {claim.text}")
                if conf_summary:
                    lines.append(f"> Confidence: {conf_summary}")
                if claim.falsifier:
                    lines.append(f"> Falsifier: *{claim.falsifier}*")
                lines.append("")

        if graph.evidence:
            lines.append("### Evidence\n")
            for ev in graph.evidence:
                lines.append(
                    f"**[{ev.id}]** `{ev.type.value}`  "
                    f"*(introduced round {ev.round_introduced} by {ev.proposer})*"
                )
                lines.append(f"> {ev.text}")
                lines.append(f"> Source: {ev.source}")
                lines.append("")

        # --- Per-agent verdicts ---
        lines.append("## Agent Verdicts\n")
        for verdict in verdicts:
            lines.append(f"### Agent: `{verdict.agent_id}`\n")
            lines.append(f"**Final position:** {verdict.final_position}\n")

            if verdict.original_claims_surviving:
                lines.append("**Claims that survived scrutiny:**")
                for c in verdict.original_claims_surviving:
                    lines.append(f"- `{c.get('claim_id', '?')}`: {c.get('reasoning', '')}")
                lines.append("")

            if verdict.original_claims_abandoned:
                lines.append("**Claims abandoned:**")
                for c in verdict.original_claims_abandoned:
                    lines.append(f"- `{c.get('claim_id', '?')}`: {c.get('reasoning', '')}")
                lines.append("")

            if verdict.compelling_challenges_from_others:
                lines.append("**Compelling challenges from peers:**")
                for c in verdict.compelling_challenges_from_others:
                    lines.append(
                        f"- `{c.get('claim_id', '?')}` (from `{c.get('from_agent', '?')}`): "
                        f"{c.get('reasoning', '')}"
                    )
                lines.append("")

            if verdict.rejected_challenges_from_others:
                lines.append("**Rejected challenges:**")
                for c in verdict.rejected_challenges_from_others:
                    lines.append(
                        f"- `{c.get('claim_id', '?')}` (from `{c.get('from_agent', '?')}`): "
                        f"{c.get('reasoning', '')}"
                    )
                lines.append("")

            if verdict.remaining_uncertainties:
                lines.append("**Remaining uncertainties:**")
                for u in verdict.remaining_uncertainties:
                    lines.append(f"- {u}")
                lines.append("")

            lines.append("---\n")

        (self.run_dir / "output.md").write_text("\n".join(lines))
