# Example Runs

These summaries are drawn from real artifacts under `runs/`. They show what a successful council deliberation looks like under the design in [PHILOSOPHY.md](PHILOSOPHY.md): independent Phase 1 analysis, a growing contested claim graph in Phase 2, and **distinct Phase 3 verdicts** that reflect battle-tested positions—not consensus for its own sake.

> Agents are not told they are in a debate during Phase 1. Convergence in final verdicts can happen and is itself a finding; the examples below highlight runs where models **diverged** after stress-testing.

---

## What to look for in a good run

| Phase | What success looks like |
|-------|-------------------------|
| **1 — Sealed exploration** | Each agent proposes different claims with falsifiers, without seeing peers |
| **2 — Stress-test** | Contested claims, new evidence, edges (supports/contradicts/rebuts), confidence updates across rounds |
| **3 — Verdicts** | Each agent states a final position, lists surviving vs abandoned claims, cites compelling/rejected peer challenges, names uncertainties |

Artifact paths (local): `runs/<timestamp>_<name>/output.md`, `verdicts.json`, `final_graph.json`, `transcripts/`.

---

## Example 1: Crumple vs fold (canonical multi-agent run)

**Run:** `runs/20260421_145621_my_run/`  
**Question:** *Should you crumple or fold toilet paper before use?*  
**Agents that completed:** Gemma, Elephant (others abstained on API/parse)  
**Stress-test:** 5 rounds → terminated `no_challenges`  
**Graph size:** 15 claims, 10 evidence items

### Key moment — Phase 1: independent starting positions

Agents could not see each other's output. They already disagreed on what mattered:

**Gemma** opened with a trade-off frame:
- Folding increases thickness/absorbency per square inch
- Crumpling may improve mechanical cleaning via texture
- For most users it's habit/preference unless hygiene differences are proven

**Elephant** opened with usability and structure:
- Folded sheets are easier to grasp and count
- Crumpling can add air pockets and absorbency
- Crumpled paper may tear or be used less efficiently

Same silly question, different conceptual models—before any "debate."

### Key moment — Phase 2: arbiter forces a physical trade-off

After Round 1, the arbiter saw a qualitative stalemate (density vs surface area) and issued a targeted query:

> *"Does the increased texture of crumpled paper provide a measurable advantage in removing surface contaminants that outweighs the potential loss in liquid-holding capacity caused by denser packing?"*

It also marked Gemma's crumpling/cleaning claim as **contested**. Agents responded with capillary-action vs layer-thickness arguments, empirical-style evidence (pilot material tests, fluid-dynamics reasoning), and claims like **"smear-risk coefficient"** when liquid fraction exceeds ~25–35%.

The graph ended with multiple **contested** and **open** claims—not a tidy agreement.

### Key moment — Phase 3: two battle-tested verdicts (not clones)

| Agent | Final position (summary) |
|-------|---------------------------|
| **Gemma** | Leans **folding** as the more **robust** hygienic default: predictable performance across liquid levels; crumpling risks smearing via preferential flow paths past a threshold |
| **Elephant** | **No universal winner**—choice is **context-dependent** on liquid-to-particulate load: crumple when particulate-heavy/dry; fold when liquid-heavy |

Both agents documented:
- **Surviving claims** they still defend (with reasoning per claim ID)
- **Abandoned or subsumed claims** (e.g. Gemma dropped an oversimple crumpling claim)
- **Compelling challenges from peers** (e.g. density/absorbency dispute on `c4a780db`, `224c1f55`)
- **Rejected challenges** (with rationale)
- **Remaining uncertainties** (e.g. exact Liquid Fraction Threshold across paper brands)

That structure is the intended output: auditable disagreement after scrutiny.

---

## Example 2: Optimal sandwich (meta-reasoning + peer challenge)

**Run:** `runs/20260421_144320_my_run/`  
**Question:** *What is the most optimal way to make a sandwich?*  
**Agents that completed:** Gemma, Elephant  
**Stress-test:** 2 rounds → `low_update_rate`  
**Graph size:** 8 claims, 9 evidence items

### Key moment — Phase 1: reframing the question

Both agents refused to pick "the best method" without defining what "optimal" means:

- **Gemma:** optimal depends on objective function (taste vs speed); moisture barriers against bread; alternating textures for flavor
- **Elephant:** no universal method; Pareto trade-offs; clustering vs alternating layers disputed

### Key moment — Phase 2: contested flavor theory

Gemma's claim that optimal flavor requires **alternating textures** (not clustering) became **contested** when Elephant pointed to counterexamples (e.g. caprese: clustered tomato/mozzarella/basil). The graph held both the rule and the exception in tension.

### Key moment — Phase 3: same impossibility result, different frames

| Agent | Final position (summary) |
|-------|---------------------------|
| **Gemma** | Optimality is a **time-dependent multi-objective** problem—moisture migration and structural integrity shift the Pareto frontier over time |
| **Elephant** | No universal method; optimality is **contingent on stated metrics** and temporal constraints; moisture shifts what's Pareto-optimal |

Shared conclusion ("no single best way") but **different verdict architecture**: Gemma abandoned the alternating-textures claim as too absolute; Elephant kept a broader "no universal prescription" frame. Both cite peer challenges on claim `72b86ced`.

---

## Example 3: qEEG biomarkers (single agent, high-substance)

**Run:** `runs/20260422_144540_my_run/`  
**Question:** *(clinical/research question on qEEG biomarkers for Alzheimer's/MCI)*  
**Agents that completed:** Gemma only  
**Stress-test:** 2 rounds → `low_update_rate`

Useful for showing **depth on a hard domain** when only one model finishes:

- **Final position:** No single qEEG biomarker is a gold standard vs CSF/PET; spectral slowing is consistent but non-specific; **composite ML classifiers** outperform single features
- **Abandoned claim** after scrutiny: theta/alpha as "most consistent" marker—challenged by literature favoring delta in some cohorts
- **Surviving claims:** multivariate AUC advantage, non-specificity for DLB vs AD, composite-model recommendation

Good for protocol/verdict structure; not a multi-agent divergence demo.

---

## Mock runs (`--mock`): identical output by design

The mock provider (`src/council/mock/stubs.py`) returns **fixed canned JSON** for every agent and role. All agents get the same Phase 1/2/3 templates, so **identical verdicts across agents are expected**—not a bug or convergence signal.

Example: `runs/20260524_095502_my_run/` — every agent ends with the same Phase 3 boilerplate about needing "contextual specificity."

**Use mock for:** verifying install, CI, artifact layout, and pipeline wiring.  
**Do not use mock for:** judging debate quality, model divergence, or what live deliberation looks like.

---

## Live runs: when identical verdicts are informative

On **live** runs, agents call real models. If Phase 3 verdicts are verbatim copies across agents, that may indicate early abstentions, rate-limit damage, thin debate, or models collapsing to a safe template—not independent agreement.

Some multi-agent runs on the default nuclear prompt (`prompts/example.txt`) showed this pattern in April 2026 artifacts (e.g. several agents all returning the same "contextual specificity" verdict). That is worth investigating on live runs only; it does **not** apply to `--mock`.

---

## How to reproduce

```bash
# Dry run — canned responses; identical agent outputs are expected
council run --mock

# Live run (needs OPENROUTER_API_KEY; use 2–3 capable models for best results)
council run --prompt "Should you crumple or fold toilet paper before use?"
```

After a **live** run, open `runs/<latest>/output.md` and check that Phase 3 verdicts differ in substance. Mock runs will not differ—that is normal.

---

## Further reading

- [PHILOSOPHY.md](PHILOSOPHY.md) — core design intent
- [ARCHITECTURE.md](ARCHITECTURE.md) — how phases and roles connect
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) — rate limits, dedup, and other iteration notes
