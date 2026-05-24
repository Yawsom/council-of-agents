# Architecture

This document explains how the codebase is organized and how a deliberation run flows through it. Read this before diving into individual modules.

## Mental model

The system has three layers:

```
┌─────────────────────────────────────────────────────────────┐
│  Entry & wiring          cli.py                             │
├─────────────────────────────────────────────────────────────┤
│  Pipeline (when)         orchestration/phase{1,2,3}.py      │
├─────────────────────────────────────────────────────────────┤
│  Roles (who)             agents/, arbiter/, observer/       │
│  Protocol (what format)  agents/prompts.py, agents/parser.py│
├─────────────────────────────────────────────────────────────┤
│  Shared state            graph/                               │
│  Claim dedup             identity/                            │
│  Version B experiments   manipulation/                        │
│  I/O                     artifacts/, config/                  │
│  LLM transport           providers/, mock/                    │
└─────────────────────────────────────────────────────────────┘
```

**Important naming note:** The `agents/` package is not only "debating agents." It holds the shared LLM **protocol** — prompts and JSON parsers used by council members, the arbiter, and the observer. Role-specific runtime classes live in `agents/agent.py` (council), `arbiter/`, and `observer/`.

## Run lifecycle

A single run is orchestrated by `cli._run_council()`:

1. Load config and build provider, embedder, agents, arbiter, observer
2. Optionally build `DisguisePipeline` when `version: B`
3. **Phase 1** — sealed exploration; populate the graph
4. **Version B prep** — disguise each agent's Phase 1 claims for injection
5. **Phase 2** — stress-test loop until termination
6. **Phase 3** — collect final verdicts
7. Write artifacts via `ArtifactsWriter`

## Phase 1: Sealed exploration

**File:** `orchestration/phase1.py`

Each council agent receives the question independently. No agent sees peer output.

Per agent:
1. Build prompt from `agents/prompts.py`
2. Call LLM via `SubAgent.call()`
3. Parse JSON via `agents/parser.parse_phase1()`
4. On parse failure: one reformat retry, then mark agent `excluded`

Graph ingestion:
- New claims pass through `identity.check_identity()` (embedding similarity + optional LLM disambiguation)
- Duplicates merge into existing claims; unique claims become new nodes
- Evidence nodes are added without deduplication

Agents that timeout, fail API calls, or fail parsing twice are excluded from later phases.

## Phase 2: Stress-test loop

**File:** `orchestration/phase2.py`

Each round follows this order:

```
Agents (parallel, staggered)
  → ingest claims / evidence / edges / position updates
Arbiter
  → targeted query for next round; optional graph ops; may terminate early
Observer (every N rounds)
  → faithfulness checks; may abort the run
Termination check
  → max rounds, no new claims, no challenges, low update rate
```

### What agents see

- **Version A:** `graph/serializer.serialize_open_state()` — the real shared graph
- **Version B:** `manipulation/disguise.inject_for_agent()` — graph with disguised self-claims injected as a synthetic peer

### Termination reasons

| Reason | Trigger |
|--------|---------|
| `max_rounds` | Reached `termination.max_rounds` |
| `no_new_claims` | Fewer new claims than `min_new_claims_per_round` |
| `no_challenges` | No contradict/rebut edges for `no_challenge_rounds` consecutive rounds |
| `low_update_rate` | Position update rate below threshold (after round 1) |
| `arbiter_terminate` / `arbiter_abort` | Arbiter signals end |
| `observer_abort` | Observer flags a critical faithfulness issue |
| `all_abstained` | Every active agent failed or abstained |

### Ingestion rules worth knowing

- **Edges** referencing unknown node IDs are skipped with a warning
- **Position updates** only apply to claims the agent originally proposed (`agent.claim_ids`)
- **Challenge edges** (`contradicts`, `rebuts`) mark target claims as contested

## Phase 3: Verdicts

**File:** `orchestration/phase3.py`

Each non-excluded agent reviews the final graph and submits a structured verdict: surviving claims, abandoned claims, compelling/rejected peer challenges, remaining uncertainties.

The observer optionally runs a `verdict_grounding` check on each verdict.

## Package reference

| Package | Responsibility |
|---------|----------------|
| `cli.py` | Typer commands, dependency wiring, artifact finalization |
| `orchestration/` | Phase runners; owns the deliberation control flow |
| `agents/agent.py` | `SubAgent` — council member LLM calls, cost tracking, exclusion state |
| `agents/prompts.py` | System/user prompt templates for all roles and phases |
| `agents/parser.py` | JSON extraction and schema validation for all LLM responses |
| `arbiter/` | Provocateur: targeted queries, graph operations, early termination |
| `observer/` | Auditor: faithfulness and verdict grounding checks |
| `graph/` | Claim graph data model, edge validation, prompt serialization |
| `identity/` | Embedding-based claim deduplication during ingestion |
| `manipulation/` | Version B disguise pipeline (synthetic peer injection) |
| `providers/` | `LLMProvider` abstraction; OpenRouter implementation |
| `mock/` | Canned responses for dry runs (`--mock`) |
| `artifacts/` | Writes run output to `runs/<timestamp>_<name>/` |
| `config/` | Pydantic schemas and YAML loading |

## Graph model

**Files:** `graph/nodes.py`, `graph/edges.py`, `graph/graph.py`

Node types:
- **Claim** — atomic arguable statement; has status (`open`, `contested`, `resolved`), per-agent confidence, falsifier
- **Evidence** — supporting data with source attribution
- **Assumption** — implicit premise underpinning claims

Edge types:
- `supports`, `contradicts`, `rebuts`, `depends_on`

The graph is the single source of truth shared across all phases. Agents never mutate each other's state directly — they propose structured updates that orchestration ingests.

## LLM call pattern

All roles follow the same pattern (implemented separately in each module):

```
build prompt → provider.call(json_mode=True) → parse → retry once on failure → abstain
```

Council agents use `SubAgent.call()` / `retry_with_reformat()`. Arbiter and observer call the provider directly with their own parsers.

## Configuration

**Files:** `config/schema.py`, `config/loader.py`

`RunConfig` is the top-level schema. API keys resolve from YAML or environment (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`).

Experiment batches (`experiments/*.yaml`) define a shared `base` config plus per-run entries with optional `roster` and `overrides`.

## Artifacts

**File:** `artifacts/writer.py`

Each run gets a timestamped directory. Phase 1 and Phase 2 write incremental snapshots; the CLI writes final summaries after Phase 3.

Key outputs: `final_graph.json`, `verdicts.json`, `output.md`, `cost_summary.json`.

## Where to start reading code

| Goal | Start here |
|------|------------|
| Understand a full run | `cli.py` → `_run_council()` |
| Follow the debate loop | `orchestration/phase2.py` → `run_phase2()` |
| See what agents receive | `graph/serializer.py` |
| Understand response formats | `agents/prompts.py`, `agents/parser.py` |
| Version B manipulation | `manipulation/disguise.py`, `phase2._call_agent_phase2()` |
