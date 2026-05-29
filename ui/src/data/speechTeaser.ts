import type {
  ArbiterOutput,
  ObserverCheck,
  Phase1Transcript,
  Phase2Transcript,
  Verdict,
} from "@/types/artifacts";

function truncate(s: string, max = 72): string {
  const t = s.replace(/\s+/g, " ").trim();
  return t.length <= max ? t : `${t.slice(0, max - 1)}…`;
}

export function agentTeaser(
  transcript: Phase1Transcript | Phase2Transcript | undefined
): string {
  if (!transcript) return "…";
  if (transcript.new_claims?.length) {
    return truncate(transcript.new_claims[0].text);
  }
  if (transcript.position_updates?.length) {
    const u = transcript.position_updates[0] as { reasoning?: string };
    return truncate(u.reasoning ?? "Updated position");
  }
  if (transcript.scratchpad) {
    return truncate(transcript.scratchpad);
  }
  return "Listening…";
}

export function arbiterTeaser(arbiter: ArbiterOutput | undefined): string {
  if (!arbiter) return "Observing the chamber…";
  if (arbiter.targeted_query) return truncate(arbiter.targeted_query);
  if (arbiter.termination_signal && arbiter.termination_signal !== "continue") {
    return `Signal: ${arbiter.termination_signal}`;
  }
  return truncate(arbiter.scratchpad ?? "Provoking debate…");
}

export function observerTeaser(checks: ObserverCheck[] | undefined): string {
  if (!checks?.length) return "Standing audit…";
  const failed = checks.filter((c) => !c.passed).length;
  const issues = checks.reduce((n, c) => n + (c.issues?.length ?? 0), 0);
  if (failed > 0) return `${failed} check(s) flagged · ${issues} issue(s)`;
  return `All ${checks.length} check(s) passed`;
}

export function verdictTeaser(verdict: Verdict | undefined): string {
  if (!verdict) return "Delivering verdict…";
  return truncate(verdict.final_position);
}
