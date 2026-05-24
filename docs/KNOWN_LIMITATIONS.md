# Known Limitations (Developer Reference)

Working document for iteration — not user-facing documentation. See [README](../README.md#known-limitations) for the public summary.

Last reviewed: 2026-05-24

---

## Security and operations

### OpenRouter-only live provider

All live LLM calls go through OpenRouter. No direct Anthropic/OpenAI provider implementations.

### Paid model access and rate limiting (active dev blocker)

OpenRouter free-tier models have unpublished, dynamic rate limits. A full run fans out across many agents plus arbiter/observer calls per round, so development is often blocked by 429s and long backoff waits rather than by code defects. Paid model access would improve test fidelity but is not always available during iteration. This is the primary practical constraint on how fast the project can be exercised end-to-end.

### No checkpoint / resume

A failure mid-run loses progress. Graph snapshots are written per round but there is no command to resume from a snapshot.

### Experiments run sequentially

`council experiment` runs entries one at a time. No parallelism for batch experiments.

---

## Claim deduplication (`identity/`)

### Cosine similarity is a coarse filter

Embedding cosine similarity is used as a fast first pass. It misses paraphrases, false-merges superficially similar claims, and only the single best-matching existing claim is considered — not all pairs.

**Exploring:** Alternative dedup approaches.

### Disambiguation is a brittle yes/no call

Borderline pairs (similarity between `similarity_low` and `similarity_high`) get a single LLM prompt asking for "Yes" or "No". No structured reasoning is persisted beyond `merge_log.json`.

### Embedding failure creates silent duplicates

If embedding fails, the claim is treated as new (`method: embedding_failure`). No retry, no fallback disambiguation.

### Null embedder disables dedup entirely

When `embedder.provider: none`, all claims are treated as distinct regardless of text overlap (except exact string match).

---

## Graph model and ingestion

### Assumptions are modeled but never ingested

`Assumption` nodes exist in `graph/nodes.py` and prompts mention `depends_on` edges to assumptions, but `orchestration/phase1.py` and `phase2.py` never call `add_assumption()`. Agents cannot create assumptions through the pipeline.

### Evidence `supports` field is not wired to edges

Phase 1 parses `supports` on evidence entries but only calls `add_evidence()`. No automatic `supports` edge is created. Agents must emit explicit edges in Phase 2.

### Invalid edges are silently dropped

If an agent references unknown node IDs, phase2 logs a warning and skips the edge. The agent receives no in-round feedback to correct the reference.

### Resolved claims disappear from agent view

`serialize_open_state()` only includes `open` and `contested` claims. Resolved claims are omitted from prompts — agents lose visibility into the full debate history.

### Unanswered-challenge detection is heuristic

In `serializer._find_unanswered_challenges()`, a challenge counts as "answered" only if something rebuts the challenger's node (`from_id`). A `supports` edge defending the target claim does not count as an answer, despite the comment suggesting it should.

### Graph size grows unbounded in prompts

Full graph serialization on every agent call. Warning logged at 500 claims; no truncation, summarization, or retrieval.

---

## LLM protocol fragility

### One parse retry, then permanent exclusion

Council agents get one JSON reformat retry. On second failure they are marked `excluded` and skipped for all subsequent phases/rounds. A transient formatting glitch permanently removes an agent.

### Arbiter failures fail open

If the arbiter can't parse its response, the round continues without a new targeted query. No retry logic (unlike council agents).

### Observer failures fail open

Observer timeout or parse error → run continues. Abort only when the observer returns `severity: error` and `recommended_action: abort`.

### No external grounding for evidence

Agents cite sources freely. The observer checks faithfulness to the graph structure, not whether cited evidence is real, current, or verifiable.

### JSON extraction is lenient

`parser._extract_json()` grabs the first `{` to last `}` in the response. Prose or multiple JSON objects can cause silent misparsing.

---

## Termination and debate dynamics

### Termination heuristics are coarse and overlapping

Phase 2 checks multiple stop conditions each round (`max_rounds`, `no_new_claims`, `no_challenges`, `low_update_rate`). They are independent — e.g. `no_new_claims` can fire even when challenges are still active.

### Position update rate uses total agent count

`update_rate = position_updates / len(agents)`, not `len(active_agents)`. Excluded agents still inflate the denominator.

### Default targeted query is static until arbiter succeeds

Round 1 starts with a hardcoded targeted query. If the arbiter abstains, the query may not update for subsequent rounds.

---

## Experiment design

### Same model across roles in default config

Gemma serves as council agent, arbiter, and observer in `config/default.yaml`. Confounds Version B studies (model auditing its own outputs in another role).

### Version B disguise can fall back to verbatim text

If rephrasing fails in `DisguisePipeline._rephrase()`, the original claim text is injected — making manipulation easier to detect and weakening the experiment.

### Version B synthetic peer is obviously synthetic

Injected claims appear under a `synthetic_peer_<hash>` ID in a separate prompt section, not as normal graph nodes. This is a deliberate design choice but limits ecological validity.

### Limited reproducibility controls

Optional per-agent `seed` exists but no run-level seed. Model weights and provider routing can change between runs. No prompt version pinning.

### Config allows 1 agent despite 2+ recommendation

Schema validator message says "at least 2" in comments but only enforces `len(agents) >= 1`. Single-agent runs are valid but meaningless for deliberation.

---

## Testing and mock fidelity

### Version B untested in CI

Integration test covers Version A only. Manipulation pipeline has no automated test.

### Mock provider homogenizes agent behavior

`MockProvider` returns nearly identical canned JSON for all agents. `--mock` validates plumbing, not model divergence or debate quality.

### No live API tests

Provider retry/backoff logic is untested against real OpenRouter responses.

---

## Priority backlog (suggested fix order)

| Priority | Item | Effort |
|----------|------|--------|
| P1 | Wire evidence `supports` → edges | Small |
| P1 | Ingest assumptions from agent output | Medium |
| P2 | Graph prompt truncation / summarization | Large |
| P2 | Separate models for agent/arbiter/observer in default config | Small |
| P2 | Version B integration test | Small |
| P3 | Checkpoint / resume from graph snapshot | Large |
| P3 | Replace cosine dedup with better approach | Research |

---

## Adding new limitations

When you discover a new limitation during iteration:

1. Add it to this file under the relevant section
2. If user-facing or safety-critical, add a one-line summary to README **Known limitations**
3. If it affects architecture assumptions, update `ARCHITECTURE.md`
