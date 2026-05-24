# Known Limitations

Council of Agents is an early research preview (v0.1). The system works end-to-end, but the items below describe real constraints you should expect when running or interpreting results.

For design intent, see [PHILOSOPHY.md](PHILOSOPHY.md). For what good output looks like, see [EXAMPLE_RUNS.md](EXAMPLE_RUNS.md).

---

## Running live experiments

### OpenRouter only

Live runs currently go through [OpenRouter](https://openrouter.ai/) only. There is no built-in direct integration with individual provider APIs (Anthropic, OpenAI, etc.).

### Rate limits and model access

Free-tier models on OpenRouter have **unpublished, dynamic rate limits**. A full council run issues many parallel and sequential LLM calls (multiple agents × multiple rounds × arbiter × observer), so runs are often slow or fail with 429 errors and long backoff waits.

The default config tunes `stagger_delay` and `max_backoff` for free models. **Reliable paid model access** improves both completion rate and debate quality.

### No resume after failure

If a run fails mid-deliberation, progress is lost. Graph snapshots are saved per round under `runs/`, but there is no command to resume from a checkpoint.

### Batch experiments are sequential

`council experiment` runs each entry one after another. There is no parallel execution for experiment batches.

---

## Mock mode (`--mock`)

The mock provider returns **fixed canned JSON** for every agent. Identical outputs across agents are **expected** — mock mode validates installation, CI, and artifact layout only.

Do **not** use `--mock` to judge debate quality, model divergence, or what live deliberation looks like. See [EXAMPLE_RUNS.md](EXAMPLE_RUNS.md#mock-runs---mock-identical-output-by-design).

---

## Claim deduplication

When agents propose new claims, the system tries to merge near-duplicates into one graph node using embedding similarity, with an LLM disambiguation step for borderline cases.

### Cosine similarity is a coarse filter

This works as a fast first pass but is **not highly accurate**:

- Paraphrases of the same idea may not merge
- Superficially similar but logically different claims may merge incorrectly
- Only the single best-matching existing claim is compared, not all pairs

Treat entries in `merge_log.json` with skepticism. Better deduplication approaches are under exploration.

### Other dedup edge cases

- **Borderline pairs** are resolved by a simple yes/no LLM call with limited reasoning recorded
- **Embedding failures** cause the claim to be added as new with no retry
- **`embedder.provider: none`** disables similarity-based dedup (exact text match only)

---

## Claim graph and ingestion

### Assumptions are not created from agent output

The graph model supports assumption nodes, and prompts mention `depends_on` edges to assumptions, but the pipeline does not yet ingest assumptions from agent responses. Only claims, evidence, and explicit edges are added automatically.

### Evidence is not auto-linked to claims

In Phase 1, evidence can include a `supports` field, but the system does not automatically create a `supports` edge. Agents must link evidence to claims explicitly in Phase 2.

### Invalid graph references are dropped

If an agent cites a claim or evidence ID that does not exist, that edge is skipped (logged as a warning). The agent does not receive in-round feedback to fix the reference.

### Resolved claims are hidden from prompts

Agents only see **open** and **contested** claims in later rounds. Resolved claims are omitted from the serialized graph view, so agents lose direct visibility into the full historical debate state.

### Long debates can outgrow context windows

The full graph is serialized into every agent prompt. There is no truncation or summarization yet. A warning is logged when claim count exceeds 500; very long runs may degrade or hit model context limits.

---

## Deliberation protocol

### Agents can be permanently excluded after one parse failure

Council agents get **one retry** if their JSON response is malformed. On a second failure they are marked excluded and skipped for the rest of the run. A transient formatting error can remove an agent entirely.

### Arbiter and observer failures are non-fatal

If the arbiter or observer fails to parse a response or times out, the run **continues** without their input for that step. The observer only aborts a run when it returns a critical error with `recommended_action: abort`.

### Evidence is not fact-checked

Agents can cite sources freely. The observer checks whether outputs are consistent with the **graph structure**, not whether cited evidence is real, current, or verifiable.

### Lenient JSON parsing

Responses are parsed by extracting the first `{` … `}` block in the text. Surrounding prose or multiple JSON objects can cause silent misparsing.

### Termination can feel abrupt

Phase 2 stops when any of several independent conditions is met (`max_rounds`, too few new claims, no challenges for N rounds, low position-update rate). These checks do not always align with intuitive “debate is done” — for example, the run may end for `no_new_claims` while challenges are still active.

### Default config uses one model in multiple roles

In `config/default.yaml`, the same model family may serve as a **council agent**, **arbiter**, and **observer**. For Version B manipulation studies, factor this into interpretation (a model may effectively audit its own outputs in another role).

### Limited reproducibility

Per-agent `seed` is optional, but there is no run-level seed or pinned prompt versioning. Model behavior and provider routing can vary between runs.

### Minimum agent count

The config allows a single agent, but deliberation requires **at least two** distinct models completing the pipeline to be meaningful. Use 2–3 capable models in a similar capability band for serious experiments.

---

## Version B (manipulation experiments)

### Disguise fallback

If claim rephrasing fails, the original claim text may be injected verbatim, which makes the manipulation easier to notice and weakens the experiment.

### Synthetic peer presentation

Disguised self-support appears under a `synthetic_peer_*` label in a separate prompt section, not as ordinary graph nodes. This is intentional for logging and analysis but reduces ecological validity compared to fully hidden manipulation.

### Less automated test coverage

Version B has less automated test coverage than Version A. Validate manipulation runs manually when experimenting.

---

## Interpreting results

| What you want | What to check |
|---------------|----------------|
| Did the pipeline work? | Artifacts exist under `runs/`, `final_graph.json`, `verdicts.json`, `output.md` |
| Did models actually disagree? | Phase 3 `final_position` fields differ in **substance** (live runs only) |
| Did stress-testing happen? | Contested claims, edges, confidence updates in `output.md` / graph snapshots |
| Was Phase 1 independent? | Different `transcripts/phase1/` outputs per agent |

Convergence after scrutiny and divergence after scrutiny are both valid outcomes. See [PHILOSOPHY.md](PHILOSOPHY.md#convergence-is-a-result-not-a-target).

---

## Reporting issues

If you hit a limitation not listed here, open an issue on the repository with the run directory name (from `runs/`), config version, and whether the run used `--mock`.
