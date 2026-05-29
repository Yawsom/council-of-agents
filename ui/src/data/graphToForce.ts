import type { GraphSnapshot, ClaimStatus, EdgeType } from "@/types/artifacts";

export const STATUS_COLORS: Record<ClaimStatus, string> = {
  open: "#c9a227",
  contested: "#e85d3a",
  supported: "#6b8f71",
  rejected: "#5c5348",
};

const EVIDENCE_COLOR = "#5a7a9a";
const ASSUMPTION_COLOR = "#9a7ab8";

export type GraphNodeKind = "claim" | "evidence" | "assumption";

export interface ForceNode {
  id: string;
  name: string;
  kind: GraphNodeKind;
  color: string;
  val: number;
  status?: ClaimStatus;
  fullText: string;
  proposer?: string;
  isNew?: boolean;
  isUpdated?: boolean;
  /** Set by force simulation at runtime */
  x?: number;
  y?: number;
}

export type LinkEndpoint = string | ForceNode;

export interface ForceLink {
  id: string;
  source: LinkEndpoint;
  target: LinkEndpoint;
  type: EdgeType;
  color: string;
  isNew?: boolean;
}

export interface ForceGraphData {
  nodes: ForceNode[];
  links: ForceLink[];
}

export function snapshotToForceGraph(
  graph: GraphSnapshot,
  diff?: {
    addedNodes: string[];
    updatedNodes: string[];
    addedEdges: string[];
  } | null
): ForceGraphData {
  const nodes: ForceNode[] = [];

  for (const claim of graph.claims) {
    nodes.push({
      id: claim.id,
      name: truncateLabel(claim.text, 52),
      kind: "claim",
      color: STATUS_COLORS[claim.status] ?? STATUS_COLORS.open,
      val: 4 + (claim.status === "contested" ? 2 : 0),
      status: claim.status,
      fullText: claim.text,
      proposer: claim.proposer,
      isNew: diff?.addedNodes.includes(claim.id),
      isUpdated: diff?.updatedNodes.includes(claim.id),
    });
  }

  for (const ev of graph.evidence) {
    nodes.push({
      id: ev.id,
      name: truncateLabel(ev.text, 44),
      kind: "evidence",
      color: EVIDENCE_COLOR,
      val: 2.5,
      fullText: ev.text,
      proposer: ev.proposer,
      isNew: diff?.addedNodes.includes(ev.id),
    });
  }

  for (const a of graph.assumptions) {
    nodes.push({
      id: a.id,
      name: truncateLabel(a.text, 24),
      kind: "assumption",
      color: ASSUMPTION_COLOR,
      val: 3,
      fullText: a.text,
      isNew: diff?.addedNodes.includes(a.id),
    });
  }

  const nodeIds = new Set(nodes.map((n) => n.id));

  const linkColor = (type: EdgeType): string => {
    if (type === "contradicts" || type === "rebuts") return "rgba(232, 93, 58, 0.65)";
    if (type === "depends_on") return "rgba(154, 122, 184, 0.55)";
    return "rgba(201, 162, 39, 0.45)";
  };

  const links: ForceLink[] = graph.edges
    .filter((e) => nodeIds.has(e.from_id) && nodeIds.has(e.to_id))
    .map((e) => ({
      id: e.id,
      source: e.from_id,
      target: e.to_id,
      type: e.type,
      color: linkColor(e.type),
      isNew: diff?.addedEdges.includes(e.id),
    }));

  return { nodes, links };
}

function truncateLabel(text: string, max: number): string {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length <= max ? t : `${t.slice(0, max - 1)}…`;
}

export function linkEndpointId(endpoint: LinkEndpoint): string {
  return typeof endpoint === "object" ? endpoint.id : endpoint;
}

/** Node ids linked to the given node (undirected). */
export function neighborIds(nodeId: string, links: ForceLink[]): Set<string> {
  const out = new Set<string>();
  for (const l of links) {
    const s = linkEndpointId(l.source);
    const t = linkEndpointId(l.target);
    if (s === nodeId) out.add(t);
    if (t === nodeId) out.add(s);
  }
  return out;
}
