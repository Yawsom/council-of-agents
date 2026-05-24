# Council of Agents

A perspective-exploration and stress-test engine that runs structured multi-model deliberations over a shared **claim graph**. Several LLMs independently analyze a question, challenge each other's claims, and deliver final verdicts — with optional manipulation experiments to study sycophancy.

> **Early research preview.** This is an early version of the project and is still in the research phase. APIs, configs, and experiment protocols may change without notice. Expect rough edges — use it for exploration and experimentation, not production workloads.

### Active development constraints

The main bottleneck right now is **access to paid models** and **aggressive rate limiting on OpenRouter** (especially on free-tier endpoints). A full council run issues many parallel and sequential LLM calls across multiple models, so development and testing progress slowly when requests are throttled or queued for long backoff windows. The default config is tuned for free models (`stagger_delay`, `max_backoff`); meaningful multi-model experiments still need reliable paid capacity. Use `--mock` for pipeline work; expect live runs to be slow or fragile until billing and rate limits are less of a constraint.

## How it works

```
Question
   │
   ▼
Phase 1 — Sealed exploration
   │  Each agent analyzes independently (no peer visibility)
   ▼
Claim graph (claims, evidence, edges)
   │
   ▼
Phase 2 — Stress-test loop
   │  Agents challenge peers; arbiter provokes; observer audits
   │  Loop until termination criteria met
   ▼
Phase 3 — Verdicts
   │  Each agent summarizes what survived scrutiny
   ▼
Artifacts written to runs/
```

### Protocol versions

| Version | Behavior |
|---------|----------|
| **A** (honest) | Agents see the real shared claim graph |
| **B** (manipulation) | Agents see disguised rephrasings of their own claims injected as fake peer support |

Version B is controlled by `manipulation.*` settings in the config and is intended for sycophancy / self-reinforcement experiments.

## Requirements

- Python 3.9+
- [OpenRouter](https://openrouter.ai/) API key for live runs (free-tier models work, but rate limits apply)
- ~22 MB disk for the default local embedding model (`all-MiniLM-L6-v2`, downloaded on first run)

## Installation

```bash
git clone <repo-url>
cd agent-council

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

## Configuration

Copy the example env file and add your key:

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY
```

Keys are read from the environment (or a `.env` file in the project root):

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENROUTER_API_KEY` | Live runs | LLM calls via OpenRouter |
| `OPENAI_API_KEY` | Optional | Embeddings when `embedder.provider: openai` |

Run settings live in YAML. See `config/default.yaml` for the full schema.

Key fields:

- `prompt` or `prompt_file` — the question under deliberation (required)
- `agents` — list of `{id, model, temperature, timeout}` entries
- `version` — `A` or `B`
- `termination` — when to stop the stress-test loop (`max_rounds`, `no_challenge_rounds`, etc.)
- `embedder.provider` — `local` (default, no API key), `openai`, `openrouter`, or `none`
- `rate_limits` — stagger delay and backoff for free-tier models

## Usage

### Dry run (no API calls)

```bash
council run --mock
```

Uses canned responses from the mock provider. Good for verifying installation and artifact output.

### Single deliberation

```bash
# Uses config/default.yaml and prompts/example.txt
council run

# Override the question or protocol version
council run --prompt "Should cities ban private cars in downtown areas?"
council run --version B

# Custom config
council run --config path/to/config.yaml
```

### Batch experiments

Run multiple A/B experiments from one file:

```bash
council experiment experiments/example.yaml
council experiment experiments/example.yaml --mock
```

Each experiment entry can specify a `roster` of models, a `prompt_file`, and per-run `overrides`.

## Output artifacts

Each run creates a timestamped directory under `runs/`:

```
runs/20260524_143022_my_run/
├── config.yaml              # Effective config snapshot
├── final_graph.json         # Final claim graph
├── verdicts.json            # Per-agent final positions
├── output.md                # Human-readable summary
├── cost_summary.json        # Token usage and USD cost
├── merge_log.json           # Claim deduplication decisions
├── observer_log.json        # Observer audit findings
├── manipulation_log.json    # Version B only
├── graph_snapshots/         # Graph state per round
└── transcripts/
    ├── phase1/              # Initial agent outputs
    └── round_N/             # Per-round agent, arbiter, observer outputs
```

## Development

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=council --cov-report=term-missing
```

### Architecture guide

For a module-by-module walkthrough of how a run flows through the codebase, see **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

For a full working list of known gaps and iteration backlog, see **[docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)** (developer reference).

Key convention: the `agents/` package holds the shared LLM protocol (prompts + parsers) used by council members, the arbiter, and the observer. Role-specific runtime classes live in `agents/agent.py`, `arbiter/`, and `observer/`.

## Project structure

```
src/council/
├── cli.py                 # Entry point — wires config, providers, phases
├── orchestration/         # Phase 1, 2, 3 pipeline (see docs/ARCHITECTURE.md)
├── graph/                 # Claim graph (nodes, edges, serializer)
├── agents/                # SubAgent runtime + shared prompts/parsers
├── arbiter/               # Provocateur that drives the debate
├── observer/              # Auditor for grounding and consistency
├── identity/              # Embedding-based claim deduplication
├── manipulation/          # Version B disguise pipeline
├── providers/             # OpenRouter client with retry/backoff
├── artifacts/             # Run output writer
├── config/                # Pydantic schema and YAML loader
└── mock/                  # Mock provider for dry runs

docs/
├── ARCHITECTURE.md        # Module guide and run lifecycle
└── KNOWN_LIMITATIONS.md   # Developer reference — full limitation backlog

config/                    # Default run configuration
experiments/               # Batch experiment definitions
prompts/                   # Example deliberation questions
tests/                     # Unit and integration tests
```

## Tips

- **Mix models in a similar capability band.** Pairing frontier models with small open models degrades debate quality.
- **Free-tier models need patience.** The default `rate_limits.stagger_delay` and `max_backoff` are tuned for OpenRouter free models.
- **Start with `--mock`** before spending API credits. Then try 2–3 agents before scaling to the full 6-model roster in `config/default.yaml`.
- **Version B interpretation:** The arbiter/observer model (Gemma in the default config) also participates as an agent — factor that into experiment analysis.

## Known limitations

- **Claim deduplication uses cosine similarity as a coarse filter.** When agents propose new claims, `identity/` compares embedding vectors and uses cosine similarity to decide whether two statements might be the same assertion. This works as a fast first pass but is not particularly accurate — paraphrases can score low, while superficially similar but logically distinct claims can score high. Borderline cases fall through to an LLM disambiguation call, but the embedding step still shapes which pairs get reviewed. Alternative deduplication approaches are under exploration; treat merge decisions in `merge_log.json` with appropriate skepticism.

- **Assumptions are modeled but not ingested.** The graph supports assumption nodes and `depends_on` edges, but the orchestration pipeline never creates assumptions from agent output — only claims, evidence, and explicit edges.

- **Evidence is not auto-linked to claims.** Phase 1 accepts a `supports` field on evidence, but no edge is created automatically. Agents must emit `supports` edges manually in Phase 2.

- **The full graph is serialized into every prompt.** As deliberations grow, context size grows with no truncation or summarization. Runs may degrade or hit context limits on long debates.

- **One JSON parse failure permanently excludes an agent.** Council agents get a single reformat retry; on second failure they are skipped for the rest of the run.

- **Default config reuses the same model across roles.** The default roster uses Gemma as a council agent, arbiter, and observer — factor this into experiment design, especially for Version B.

See **[docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md)** for the complete developer reference (protocol fragility, termination heuristics, mock fidelity, backlog, etc.).

## License

Not yet specified. Add a `LICENSE` file before distributing.
