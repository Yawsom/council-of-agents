/** Artifact schemas — duplicated from council JSON output; no Python imports. */

export type ClaimType = "fact" | "value" | "policy" | "causal";
export type ClaimStatus = "open" | "contested" | "supported" | "rejected";
export type EvidenceType = "empirical" | "testimony" | "statistical" | "logical";
export type EdgeType = "supports" | "contradicts" | "rebuts" | "depends_on";

export interface Claim {
  id: string;
  text: string;
  type: ClaimType;
  proposer: string;
  round_introduced: number;
  status: ClaimStatus;
  per_agent_confidence: Record<string, number | null>;
  falsifier: string | null;
  merged_phrasings?: string[];
}

export interface Evidence {
  id: string;
  text: string;
  source: string;
  type: EvidenceType;
  proposer: string;
  round_introduced: number;
  per_agent_reliability: Record<string, number | null>;
}

export interface Assumption {
  id: string;
  text: string;
  held_by: string[];
  challenged: boolean;
}

export interface GraphEdge {
  id: string;
  type: EdgeType;
  from_id: string;
  to_id: string;
  rationale: string;
  proposer: string;
  round_introduced: number;
}

export interface GraphSnapshot {
  claims: Claim[];
  evidence: Evidence[];
  assumptions: Assumption[];
  edges: GraphEdge[];
}

export interface AgentConfig {
  id: string;
  model: string;
  temperature?: number;
  timeout?: number;
}

export interface RunConfig {
  name?: string;
  prompt?: string;
  prompt_file?: string;
  version?: string;
  agents: AgentConfig[];
  arbiter_model?: string;
  observer_model?: string;
}

export interface Phase1Transcript {
  agent_id: string;
  round: number;
  scratchpad?: string;
  new_claims?: Array<{
    text: string;
    type: string;
    confidence?: number;
    falsifier?: string | null;
  }>;
  new_evidence?: Array<{
    text: string;
    source: string;
    type: string;
    supports?: string | null;
  }>;
  new_edges?: unknown[];
  position_updates?: unknown[];
}

export interface Phase2Transcript extends Phase1Transcript {
  new_edges?: Array<{
    type: EdgeType;
    from: string;
    to: string;
    rationale: string;
  }>;
  position_updates?: Array<{
    claim_id: string;
    new_confidence: number;
    triggered_by: string;
    reasoning: string;
  }>;
}

export interface ArbiterOutput {
  scratchpad?: string;
  targeted_query?: string;
  graph_operations?: {
    merges?: Array<{ claim_ids: string[]; rationale: string }>;
    status_changes?: Array<{
      claim_id: string;
      new_status: ClaimStatus;
      rationale: string;
    }>;
  };
  termination_signal?: string;
  termination_reasoning?: string;
  warnings?: string[];
}

export interface ObserverCheck {
  round: number;
  check_type: string;
  subject_id: string;
  passed: boolean;
  issues: Array<{ severity: string; description: string }>;
  recommended_action?: string;
}

export interface Verdict {
  agent_id: string;
  final_position: string;
  original_claims_surviving?: Array<{ claim_id: string; reasoning: string }>;
  original_claims_abandoned?: Array<{ claim_id: string; reasoning: string }>;
  compelling_challenges_from_others?: Array<{
    claim_id: string;
    from_agent: string;
    reasoning: string;
  }>;
  rejected_challenges_from_others?: Array<{
    claim_id: string;
    from_agent: string;
    reasoning: string;
  }>;
  remaining_uncertainties?: string[];
}

export type TimelinePhase = "phase1" | "round" | "verdicts";

export interface TimelineStep {
  id: string;
  phase: TimelinePhase;
  label: string;
  round?: number;
  graph: GraphSnapshot;
  agentTranscripts: Record<string, Phase1Transcript | Phase2Transcript>;
  arbiter?: ArbiterOutput;
  observer?: ObserverCheck[];
  verdicts?: Verdict[];
}

export interface LoadedRun {
  name: string;
  config: RunConfig;
  steps: TimelineStep[];
  source: "folder" | "fixture" | "dev";
}

export interface FileEntry {
  path: string;
  name: string;
  getText: () => Promise<string>;
}
