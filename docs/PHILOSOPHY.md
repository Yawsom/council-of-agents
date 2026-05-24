# Philosophy

Council of Agents is a **perspective-exploration** engine, not a consensus bot. Several heterogeneous LLMs analyze a question, stress-test each other's claims, and deliver **separate battle-tested verdicts**. The goal is to surface durable disagreements, abandoned claims, and what survived scrutiny — not to merge opinions into one answer.

---

## Explore first, debate second

In Phase 1, each agent analyzes the question in **isolation**. They are not told they are in a multi-agent debate. The point is to capture genuine independent reasoning before social pressure enters.

Only in Phase 2 do agents see peer claims — and even then, the protocol does not reward agreement.

---

## Claims, not vibes

Reasoning is structured as **atomic claims** with falsifiers, evidence, and edges (`supports`, `contradicts`, `rebuts`). Everything lands in a shared **claim graph** so arguments can be challenged, tracked, and audited — not lost in chat history.

Every claim should be falsifiable: a concrete condition under which the agent would abandon it.

---

## Stress-test, don't harmonize

Phase 2 exists to **attack weak assumptions**. Agents have no protocol incentive to agree with each other.

- The **arbiter** provokes unresolved tensions and issues targeted queries each round.
- The **observer** audits faithfulness and can abort on critical inconsistencies.

A good run produces **multiple distinct verdicts** — each agent reporting:

- what they still defend
- what they abandoned under scrutiny
- which peer challenges they found compelling (or rejected)
- what remains uncertain

---

## Convergence is a result, not a target

If models independently reach similar conclusions **after** scrutiny, that is informative.

If they diverge, that is often **more** informative.

Both outcomes are valid research signals. The system is designed to make either outcome **auditable** in the artifacts, not to steer toward one or the other.

---

## Manipulation as experiment

**Version B** optionally injects disguised self-reinforcement: agents see rephrased versions of their own claims presented as fake peer support.

This is not the default protocol. It exists to study **sycophancy** and epistemic resilience under manipulated social proof — comparing Version A (honest graph) against Version B on the same question and roster.

---

## What a successful run looks like

| Phase | Signal of success |
|-------|-------------------|
| **1** | Different initial claims per agent (sealed exploration) |
| **2** | Contested claims, new evidence, edges, confidence updates across rounds |
| **3** | Verdicts that **differ in substance** — not copy-paste agreement |

See [EXAMPLE_RUNS.md](EXAMPLE_RUNS.md) for summaries of real runs that demonstrate this.

**Mock runs (`--mock`)** use canned responses; identical agent outputs are expected and do not reflect live debate dynamics.

---

## Related docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — how phases and modules implement this design
- [EXAMPLE_RUNS.md](EXAMPLE_RUNS.md) — concrete run summaries
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) — current constraints and caveats
