import type {
  ArbiterOutput,
  GraphSnapshot,
  ObserverCheck,
  Phase1Transcript,
  Phase2Transcript,
  TimelineStep,
  Verdict,
} from "@/types/artifacts";

const emptyGraph = (): GraphSnapshot => ({
  claims: [],
  evidence: [],
  assumptions: [],
  edges: [],
});

export interface TimelineInput {
  phase1Graph?: GraphSnapshot;
  phase1Transcripts: Record<string, Phase1Transcript>;
  rounds: Array<{
    round: number;
    agents: Record<string, Phase2Transcript>;
    arbiter?: ArbiterOutput;
    observer?: ObserverCheck[];
    graph?: GraphSnapshot;
  }>;
  finalGraph: GraphSnapshot;
  verdicts?: Verdict[];
}

export function buildTimeline(input: TimelineInput): TimelineStep[] {
  const steps: TimelineStep[] = [];
  let lastGraph = emptyGraph();

  if (input.phase1Graph || Object.keys(input.phase1Transcripts).length > 0) {
    const graph = input.phase1Graph ?? lastGraph;
    lastGraph = graph;
    steps.push({
      id: "phase1",
      phase: "phase1",
      label: "Phase 1 — Sealed",
      graph,
      agentTranscripts: { ...input.phase1Transcripts },
    });
  }

  for (const round of input.rounds) {
    const graph = round.graph ?? lastGraph;
    lastGraph = graph;
    steps.push({
      id: `round_${round.round}`,
      phase: "round",
      label: `Round ${round.round}`,
      round: round.round,
      graph,
      agentTranscripts: { ...round.agents },
      arbiter: round.arbiter,
      observer: round.observer,
    });
  }

  steps.push({
    id: "verdicts",
    phase: "verdicts",
    label: "Verdicts",
    graph: input.finalGraph,
    agentTranscripts: {},
    verdicts: input.verdicts ?? [],
  });

  return steps;
}
