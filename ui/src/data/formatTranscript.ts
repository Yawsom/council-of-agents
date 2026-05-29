import type {
  ArbiterOutput,
  GraphSnapshot,
  ObserverCheck,
  Phase1Transcript,
  Phase2Transcript,
  Verdict,
} from "@/types/artifacts";

export function shortAgentId(id: string): string {
  return id.replace(/^agent_/, "").replace(/_/g, " ");
}

export function resolveClaimText(graph: GraphSnapshot | null, claimId: string): string {
  if (!graph) return claimId;
  const c = graph.claims.find((x) => x.id === claimId);
  if (c) return c.text.length > 60 ? `${c.text.slice(0, 59)}…` : c.text;
  return claimId.replace(/^claim:/, "");
}

export interface FormattedSection {
  heading?: string;
  items: FormattedItem[];
}

export interface FormattedItem {
  kind: "text" | "claim" | "evidence" | "edge" | "update" | "list" | "badge";
  text: string;
  meta?: string;
  tone?: "neutral" | "positive" | "negative" | "warn";
}

export function formatAgentTranscript(
  t: Phase1Transcript | Phase2Transcript,
  graph: GraphSnapshot | null
): FormattedSection[] {
  const sections: FormattedSection[] = [];

  if (t.scratchpad?.trim()) {
    sections.push({
      heading: "Reasoning",
      items: [{ kind: "text", text: t.scratchpad.trim(), tone: "neutral" }],
    });
  }

  if (t.new_claims?.length) {
    sections.push({
      heading: "Claims introduced",
      items: t.new_claims.map((c) => ({
        kind: "claim" as const,
        text: c.text,
        meta: `${c.type}${c.confidence != null ? ` · ${Math.round(c.confidence * 100)}% confidence` : ""}`,
        tone: "neutral" as const,
      })),
    });
    const falsifiers = t.new_claims.filter((c) => c.falsifier);
    if (falsifiers.length) {
      sections.push({
        heading: "What would change their mind",
        items: falsifiers.map((c) => ({
          kind: "text" as const,
          text: c.falsifier!,
          meta: `on: “${c.text.slice(0, 50)}${c.text.length > 50 ? "…" : ""}”`,
          tone: "warn" as const,
        })),
      });
    }
  }

  if (t.new_evidence?.length) {
    sections.push({
      heading: "Evidence cited",
      items: t.new_evidence.map((e) => ({
        kind: "evidence" as const,
        text: e.text,
        meta: `${e.type} · ${e.source}${e.supports ? ` · supports ${resolveClaimText(graph, e.supports)}` : ""}`,
      })),
    });
  }

  const p2 = t as Phase2Transcript;
  if (p2.new_edges?.length) {
    sections.push({
      heading: "Relationships asserted",
      items: p2.new_edges.map((e) => ({
        kind: "edge" as const,
        text: e.rationale,
        meta: `${e.type}: ${resolveClaimText(graph, e.from)} → ${resolveClaimText(graph, e.to)}`,
        tone: e.type === "contradicts" || e.type === "rebuts" ? "negative" : "neutral",
      })),
    });
  }

  if (p2.position_updates?.length) {
    sections.push({
      heading: "Confidence updates",
      items: p2.position_updates.map((u) => ({
        kind: "update" as const,
        text: u.reasoning,
        meta: `${resolveClaimText(graph, u.claim_id)} → ${Math.round(u.new_confidence * 100)}% (triggered by ${resolveClaimText(graph, u.triggered_by)})`,
      })),
    });
  }

  if (sections.length === 0) {
    sections.push({
      items: [{ kind: "text", text: "No new output this step.", tone: "neutral" }],
    });
  }

  return sections;
}

export function formatVerdict(v: Verdict, graph: GraphSnapshot | null): FormattedSection[] {
  const sections: FormattedSection[] = [
    {
      heading: "Final position",
      items: [{ kind: "text", text: v.final_position, tone: "positive" }],
    },
  ];

  if (v.original_claims_surviving?.length) {
    sections.push({
      heading: "Still defending",
      items: v.original_claims_surviving.map((x) => ({
        kind: "claim",
        text: resolveClaimText(graph, x.claim_id),
        meta: x.reasoning,
        tone: "positive",
      })),
    });
  }

  if (v.original_claims_abandoned?.length) {
    sections.push({
      heading: "Abandoned",
      items: v.original_claims_abandoned.map((x) => ({
        kind: "claim",
        text: resolveClaimText(graph, x.claim_id),
        meta: x.reasoning,
        tone: "negative",
      })),
    });
  }

  if (v.compelling_challenges_from_others?.length) {
    sections.push({
      heading: "Accepted challenges",
      items: v.compelling_challenges_from_others.map((x) => ({
        kind: "text",
        text: x.reasoning,
        meta: `from ${shortAgentId(x.from_agent)} on ${resolveClaimText(graph, x.claim_id)}`,
        tone: "warn",
      })),
    });
  }

  if (v.rejected_challenges_from_others?.length) {
    sections.push({
      heading: "Rejected challenges",
      items: v.rejected_challenges_from_others.map((x) => ({
        kind: "text",
        text: x.reasoning,
        meta: `from ${shortAgentId(x.from_agent)}`,
        tone: "neutral",
      })),
    });
  }

  if (v.remaining_uncertainties?.length) {
    sections.push({
      heading: "Still uncertain",
      items: v.remaining_uncertainties.map((u) => ({
        kind: "list",
        text: u,
      })),
    });
  }

  return sections;
}

export function formatArbiter(a: ArbiterOutput, graph: GraphSnapshot | null): FormattedSection[] {
  const sections: FormattedSection[] = [];

  if (a.targeted_query?.trim()) {
    sections.push({
      heading: "Question to the council",
      items: [{ kind: "text", text: a.targeted_query.trim(), tone: "warn" }],
    });
  }

  if (a.scratchpad?.trim()) {
    sections.push({
      heading: "Provocation notes",
      items: [{ kind: "text", text: a.scratchpad.trim() }],
    });
  }

  const changes = a.graph_operations?.status_changes ?? [];
  if (changes.length) {
    sections.push({
      heading: "Graph updates",
      items: changes.map((c) => ({
        kind: "badge",
        text: resolveClaimText(graph, c.claim_id),
        meta: `→ ${c.new_status}: ${c.rationale}`,
        tone: c.new_status === "contested" ? "warn" : "neutral",
      })),
    });
  }

  const merges = a.graph_operations?.merges ?? [];
  if (merges.length) {
    sections.push({
      heading: "Merge proposals",
      items: merges.map((m) => ({
        kind: "text",
        text: m.rationale,
        meta: m.claim_ids.map((id) => resolveClaimText(graph, id)).join(" + "),
      })),
    });
  }

  if (a.termination_signal && a.termination_signal !== "continue") {
    sections.push({
      heading: "Termination",
      items: [
        {
          kind: "badge",
          text: a.termination_signal,
          meta: a.termination_reasoning,
          tone: a.termination_signal === "abort" ? "negative" : "warn",
        },
      ],
    });
  }

  if (a.warnings?.length) {
    sections.push({
      heading: "Warnings",
      items: a.warnings.map((w) => ({ kind: "text", text: w, tone: "warn" })),
    });
  }

  if (sections.length === 0) {
    sections.push({ items: [{ kind: "text", text: "Observing — no intervention this round." }] });
  }

  return sections;
}

export function formatObserver(checks: ObserverCheck[]): FormattedSection[] {
  return [
    {
      items: checks.map((c) => ({
        kind: "badge" as const,
        text: `${shortAgentId(c.subject_id)} — ${c.check_type.replace(/_/g, " ")}`,
        meta:
          c.passed
            ? "Passed"
            : c.issues.map((i) => `[${i.severity}] ${i.description}`).join("; ") ||
              "Failed",
        tone: (c.passed ? "positive" : "negative") as FormattedItem["tone"],
      })),
    },
  ];
}
