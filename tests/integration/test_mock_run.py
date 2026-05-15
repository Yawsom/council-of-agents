import asyncio
import json
import pytest
from pathlib import Path

from council.config.loader import load_run_config_from_dict
from council.graph.graph import ClaimGraph
from council.agents.agent import SubAgent
from council.arbiter.arbiter import Arbiter
from council.observer.observer import Observer
from council.artifacts.writer import ArtifactsWriter
from council.identity.embedder import NullEmbedder
from council.mock.stubs import MockProvider
from council.orchestration.phase1 import run_phase1
from council.orchestration.phase2 import run_phase2
from council.orchestration.phase3 import run_phase3


MOCK_CONFIG = {
    "name": "test_run",
    "mock": True,
    "version": "A",
    "prompt": "Should nuclear power be expanded as part of a clean energy transition?",
    "agents": [
        {"id": "agent_claude", "model": "anthropic/claude-haiku-4-5-20251001", "temperature": 0.7},
        {"id": "agent_gpt", "model": "openai/gpt-4o-mini", "temperature": 0.7},
    ],
    "arbiter_model": "anthropic/claude-haiku-4-5-20251001",
    "observer_model": "anthropic/claude-haiku-4-5-20251001",
    "observer_frequency": 1,
    "termination": {
        "min_new_claims_per_round": 0,
        "no_challenge_rounds": 2,
        "min_position_update_rate": 0.0,
        "max_rounds": 3,
    },
    "identity": {
        "similarity_high": 0.9,
        "similarity_low": 0.7,
        "disambiguation_model": "anthropic/claude-haiku-4-5-20251001",
    },
    "embedder": {"provider": "openai", "model": "text-embedding-3-small"},
    "artifacts_dir": "/tmp/council_test_runs",
}


@pytest.mark.asyncio
async def test_full_mock_run():
    config = load_run_config_from_dict(MOCK_CONFIG)
    assert config.mock is True

    round_counter = [0]
    provider = MockProvider(round_counter=round_counter)
    embedder = NullEmbedder()
    graph = ClaimGraph()
    writer = ArtifactsWriter(base_dir="/tmp/council_test_runs", run_name="test_run")

    agents = [SubAgent(a, provider) for a in config.agents]
    arbiter = Arbiter(provider=provider, model=config.arbiter_model, temperature=0.2)
    observer = Observer(provider=provider, model=config.observer_model, temperature=0.2)

    # Phase 1
    p1 = await run_phase1(
        question=config.prompt,
        agents=agents,
        graph=graph,
        embedder=embedder,
        llm_provider=provider,
        disambiguation_model=config.identity.disambiguation_model,
        identity_cfg=config.identity,
        artifacts_writer=writer,
    )
    assert len(graph.claims) > 0, "Phase 1 should produce claims"

    # Phase 2
    p2 = await run_phase2(
        question=config.prompt,
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
        artifacts_writer=writer,
    )
    assert p2.termination.reason in {
        "max_rounds", "no_new_claims", "no_challenges", "low_update_rate",
        "arbiter_terminate", "arbiter_abort", "observer_abort", "all_abstained",
    }

    # Phase 3
    p3 = await run_phase3(
        question=config.prompt,
        agents=agents,
        graph=graph,
        observer=observer,
        artifacts_writer=writer,
    )
    assert len(p3.verdicts) > 0, "Phase 3 should produce verdicts"

    # Write final artifacts
    writer.write_final_graph(graph)
    writer.write_merge_log(p2.merge_log)
    writer.write_observer_log(p2.observer_log)
    writer.write_verdicts(p3.verdicts)
    writer.write_output_md(
        question=config.prompt,
        graph=graph,
        verdicts=p3.verdicts,
        termination_reason=p2.termination.reason,
        termination_round=p2.termination.round,
    )

    run_dir = writer.run_dir
    assert (run_dir / "final_graph.json").exists(), "final_graph.json must exist"
    assert (run_dir / "verdicts.json").exists(), "verdicts.json must exist"
    assert (run_dir / "output.md").exists(), "output.md must exist"

    # Validate graph JSON is parseable
    g_data = json.loads((run_dir / "final_graph.json").read_text())
    assert "claims" in g_data

    # Validate verdicts JSON
    verdicts_data = json.loads((run_dir / "verdicts.json").read_text())
    assert isinstance(verdicts_data, list)
    assert len(verdicts_data) > 0
    assert "agent_id" in verdicts_data[0]
    assert "final_position" in verdicts_data[0]
