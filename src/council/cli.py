"""CLI entry point — wires config, providers, and the three-phase pipeline.

Commands:
  council run        — single deliberation
  council experiment — batch runs from a YAML experiment file

See docs/ARCHITECTURE.md for how modules connect.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()  # loads .env from cwd or any parent directory

from .agents.agent import SubAgent
from .arbiter.arbiter import Arbiter
from .artifacts.writer import ArtifactsWriter
from .config.loader import (
    config_snapshot_yaml,
    load_experiment_config,
    load_run_config,
    load_run_config_from_dict,
)
from .config.schema import RunConfig
from .graph.graph import ClaimGraph
from .identity.embedder import build_embedder
from .manipulation.disguise import DisguisePipeline
from .mock.stubs import MockProvider
from .observer.observer import Observer
from .orchestration.phase1 import run_phase1
from .orchestration.phase2 import run_phase2
from .orchestration.phase3 import run_phase3
from .providers.openrouter import OpenRouterProvider

app = typer.Typer(help="Council of Agents — perspective-exploration engine")
console = Console()


def _setup_logging(structured: bool = True) -> None:
    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            import time
            doc = {
                "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "msg": record.getMessage(),
            }
            if hasattr(record, "__dict__"):
                extra = {
                    k: v for k, v in record.__dict__.items()
                    if k not in logging.LogRecord.__dict__ and not k.startswith("_")
                    and k not in ("msg", "args", "exc_info", "exc_text", "stack_info", "levelname",
                                  "levelno", "pathname", "filename", "module", "funcName",
                                  "created", "msecs", "relativeCreated", "thread", "threadName",
                                  "processName", "process", "name", "lineno", "message")
                }
                if extra:
                    doc.update(extra)
            return json.dumps(doc)

    handler = logging.StreamHandler(sys.stderr)
    if structured:
        handler.setFormatter(JsonFormatter())
    logging.basicConfig(handlers=[handler], level=logging.INFO)


def _build_provider(config: RunConfig, round_counter: Optional[list[int]] = None):
    if config.mock:
        return MockProvider(round_counter=round_counter)
    if not config.openrouter_api_key:
        console.print("[red]ERROR:[/red] OPENROUTER_API_KEY not set. Use --mock for dry runs.")
        raise typer.Exit(1)
    return OpenRouterProvider(
        api_key=config.openrouter_api_key,
        max_concurrency=config.rate_limits.per_model_concurrency,
        max_backoff=config.rate_limits.max_backoff,
    )


async def _run_council(config: RunConfig, writer: ArtifactsWriter) -> dict:
    """Wire dependencies and execute phases 1 → 2 → 3, then finalize artifacts."""
    question = config.get_prompt_text()
    round_counter = [0]

    provider = _build_provider(config, round_counter)
    embedder = build_embedder(
        provider=config.embedder.provider,
        model=config.embedder.model,
        openai_api_key=config.openai_api_key,
        openrouter_api_key=config.openrouter_api_key,
    )

    agents = [
        SubAgent(agent_cfg, provider)
        for agent_cfg in config.agents
    ]
    arbiter = Arbiter(
        provider=provider,
        model=config.arbiter_model,
        temperature=config.arbiter_temperature,
        seed=config.arbiter_seed,
    )
    observer = Observer(
        provider=provider,
        model=config.observer_model,
        temperature=config.observer_temperature,
    )

    # Version B: build disguise pipeline
    disguise_pipeline = None
    if config.version == "B":
        disguise_pipeline = DisguisePipeline(
            llm_provider=provider,
            disguise_model=config.manipulation.disguise_model,
            injection_n=config.manipulation.injection_n,
            inject_every_n_rounds=config.manipulation.inject_every_n_rounds,
        )

    graph = ClaimGraph()

    console.print(f"\n[bold]Council of Agents[/bold] — Version {config.version}")
    console.print(f"Question: {question[:100]}...")
    console.print(f"Agents: {[a.id for a in agents]}\n")

    stagger = config.rate_limits.stagger_delay if not config.mock else 0.0

    abstained_agents: dict[str, list[str]] = {}  # agent_id → list of phase names

    # === Phase 1 ===
    console.print("[blue]Phase 1:[/blue] Sealed exploration...")
    p1_result = await run_phase1(
        question=question,
        agents=agents,
        graph=graph,
        embedder=embedder,
        llm_provider=provider,
        disambiguation_model=config.identity.disambiguation_model,
        identity_cfg=config.identity,
        artifacts_writer=writer,
        stagger_delay=stagger,
    )
    console.print(
        f"  Phase 1 complete. Claims: {len(graph.claims)}, Evidence: {len(graph.evidence)}"
    )
    for aid in p1_result.abstained_agents:
        abstained_agents.setdefault(aid, []).append("phase1")
    if p1_result.abstained_agents:
        console.print(f"  [yellow]Abstained:[/yellow] {p1_result.abstained_agents}")

    # Version B: prepare synthetic peers from Phase 1 claims
    if disguise_pipeline is not None:
        for agent in agents:
            await disguise_pipeline.prepare_for_agent(
                agent_id=agent.id,
                claims=[c for c in graph.claims if c.proposer == agent.id],
                round_num=0,
            )

    # === Phase 2 ===
    console.print("[blue]Phase 2:[/blue] Stress-test loop...")
    p2_result = await run_phase2(
        question=question,
        agents=agents,
        graph=graph,
        arbiter=arbiter,
        observer=observer,
        embedder=embedder,
        llm_provider=provider,
        termination_cfg=config.termination,
        identity_cfg=config.identity,
        observer_frequency=config.observer_frequency,
        disambiguation_model=config.identity.disambiguation_model,
        version=config.version,
        disguise_pipeline=disguise_pipeline,
        artifacts_writer=writer,
        stagger_delay=stagger,
    )
    round_counter[0] = p2_result.termination.round
    console.print(
        f"  Phase 2 complete. Rounds: {p2_result.termination.round}, "
        f"Reason: {p2_result.termination.reason}"
    )

    # === Phase 3 ===
    console.print("[blue]Phase 3:[/blue] Collecting verdicts...")
    p3_result = await run_phase3(
        question=question,
        agents=agents,
        graph=graph,
        observer=observer,
        artifacts_writer=writer,
        stagger_delay=stagger,
    )
    verdict_agent_ids = {v.agent_id for v in p3_result.verdicts}
    for agent in agents:
        if agent.id not in verdict_agent_ids:
            abstained_agents.setdefault(agent.id, []).append("phase3")
    for aid in p3_result.abstained_agents:
        abstained_agents.setdefault(aid, []).append("phase3")
    console.print(f"  Phase 3 complete. Verdicts: {len(p3_result.verdicts)}")

    # === Write artifacts ===
    writer.write_final_graph(graph)
    writer.write_merge_log(p2_result.merge_log)
    writer.write_observer_log(p2_result.observer_log + [i["issue"] for i in p3_result.observer_issues])

    if disguise_pipeline:
        writer.write_manipulation_log(disguise_pipeline.log)

    agent_cost_logs = [
        {"agent_id": a.id, "model": a.model, "log": a.cost_log}
        for a in agents
    ]
    writer.write_cost_summary(
        agents_cost_logs=agent_cost_logs,
        arbiter_cost_log=arbiter.cost_log,
        observer_cost_log=observer.cost_log,
    )
    writer.write_output_md(
        question=question,
        graph=graph,
        verdicts=p3_result.verdicts,
        termination_reason=p2_result.termination.reason,
        termination_round=p2_result.termination.round,
        abstained_agents=abstained_agents if abstained_agents else None,
    )

    # --- Cost summary to stdout ---
    total_cost = (
        sum(a.total_cost() for a in agents)
        + arbiter.total_cost()
        + observer.total_cost()
    )
    console.print(f"\n[bold]Cost summary:[/bold] ${total_cost:.4f} USD total")
    _print_cost_table(agents, arbiter, observer)

    return {
        "termination_reason": p2_result.termination.reason,
        "termination_round": p2_result.termination.round,
        "total_cost_usd": total_cost,
        "verdicts": len(p3_result.verdicts),
        "artifact_dir": str(writer.run_dir),
    }


def _print_cost_table(agents, arbiter, observer) -> None:
    table = Table(title="Token Usage & Cost")
    table.add_column("Component")
    table.add_column("Prompt tokens", justify="right")
    table.add_column("Completion tokens", justify="right")
    table.add_column("Cost (USD)", justify="right")

    for agent in agents:
        pt = sum(e["prompt_tokens"] for e in agent.cost_log)
        ct = sum(e["completion_tokens"] for e in agent.cost_log)
        table.add_row(f"Agent {agent.id}", str(pt), str(ct), f"${agent.total_cost():.4f}")

    arb_pt = sum(e["prompt_tokens"] for e in arbiter.cost_log)
    arb_ct = sum(e["completion_tokens"] for e in arbiter.cost_log)
    table.add_row("Arbiter", str(arb_pt), str(arb_ct), f"${arbiter.total_cost():.4f}")

    obs_ct = sum(e.get("cost_usd", 0) for e in observer.cost_log)
    table.add_row("Observer", "—", "—", f"${observer.total_cost():.4f}")

    console.print(table)


@app.command()
def run(
    config: Path = typer.Option(Path("config/default.yaml"), "--config", "-c", help="Config file path"),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Override prompt"),
    version: Optional[str] = typer.Option(None, "--version", "-v", help="Override version (A or B)"),
    mock: bool = typer.Option(False, "--mock", help="Use mock provider (no API calls)"),
    no_structured_logs: bool = typer.Option(False, "--no-structured-logs", help="Human-readable logs"),
) -> None:
    """Run a single council deliberation."""
    _setup_logging(structured=not no_structured_logs)

    run_config = load_run_config(config)
    if prompt:
        run_config.prompt = prompt
    if version:
        run_config.version = version
    if mock:
        run_config.mock = True

    writer = ArtifactsWriter(
        base_dir=run_config.artifacts_dir,
        question=run_config.get_prompt_text(),
    )

    writer.write_config_snapshot(config_snapshot_yaml(run_config))

    summary = asyncio.run(_run_council(run_config, writer))
    console.print(f"\n[green]Artifacts written to:[/green] {summary['artifact_dir']}")


@app.command()
def experiment(
    config: Path = typer.Argument(..., help="Experiment config YAML file"),
    mock: bool = typer.Option(False, "--mock", help="Use mock provider"),
) -> None:
    """Run multiple experiments sequentially from a config file."""
    _setup_logging()

    exp_config = load_experiment_config(config)
    console.print(f"[bold]Running {len(exp_config.experiments)} experiments[/bold]\n")

    summaries = []
    for i, entry in enumerate(exp_config.experiments):
        console.rule(f"Experiment {i+1}/{len(exp_config.experiments)}: {entry.name}")

        # Build run config from base + entry
        base = dict(exp_config.base)
        base["name"] = entry.name
        base["version"] = entry.version
        if entry.prompt:
            base["prompt"] = entry.prompt
        if entry.prompt_file:
            base["prompt_file"] = entry.prompt_file
        if entry.roster:
            base["agents"] = [{"id": f"agent_{m.split('/')[-1][:12]}", "model": m} for m in entry.roster]
        base.update(entry.overrides)
        if mock:
            base["mock"] = True

        run_config = load_run_config_from_dict(base)
        writer = ArtifactsWriter(
            base_dir=run_config.artifacts_dir,
            question=run_config.get_prompt_text(),
        )

        writer.write_config_snapshot(config_snapshot_yaml(run_config))

        try:
            summary = asyncio.run(_run_council(run_config, writer))
            summaries.append({"name": entry.name, "status": "ok", **summary})
        except Exception as e:
            console.print(f"[red]Experiment {entry.name} failed:[/red] {e}")
            summaries.append({"name": entry.name, "status": "error", "error": str(e)})

    # Final summary
    console.rule("All experiments complete")
    total_cost = sum(s.get("total_cost_usd", 0) for s in summaries)
    for s in summaries:
        status = "[green]OK[/green]" if s["status"] == "ok" else "[red]ERROR[/red]"
        console.print(f"  {status} {s['name']} — {s.get('termination_reason', s.get('error', ''))}")
    console.print(f"\nTotal cost: ${total_cost:.4f} USD")


if __name__ == "__main__":
    app()
