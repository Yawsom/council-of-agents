import type { GraphSnapshot } from "@/types/artifacts";

const STATUS_Y: Record<string, number> = {
  open: 0,
  contested: 80,
  supported: 160,
  rejected: 240,
};

/** Simple layered layout for claim graph nodes (no d3 dependency). */
export function layoutGraph(
  graph: GraphSnapshot,
  width: number,
  height: number
): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  const cx = width / 2;
  const cy = height / 2;

  const claims = graph.claims;
  const byStatus = new Map<string, typeof claims>();
  for (const c of claims) {
    const key = c.status;
    if (!byStatus.has(key)) byStatus.set(key, []);
    byStatus.get(key)!.push(c);
  }

  let ring = 0;
  for (const [status, list] of byStatus) {
    const baseY = STATUS_Y[status] ?? ring * 60;
    list.forEach((claim, i) => {
      const angle = (i / Math.max(list.length, 1)) * Math.PI * 2 - Math.PI / 2;
      const r = 80 + list.length * 8 + ring * 20;
      positions.set(claim.id, {
        x: cx + Math.cos(angle) * r,
        y: cy + baseY * 0.3 + Math.sin(angle) * r * 0.5,
      });
    });
    ring++;
  }

  graph.evidence.forEach((ev, i) => {
    const angle = (i / Math.max(graph.evidence.length, 1)) * Math.PI + Math.PI;
    positions.set(ev.id, {
      x: cx + Math.cos(angle) * (120 + i * 15),
      y: cy + 180 + Math.sin(angle) * 40,
    });
  });

  graph.assumptions.forEach((a, i) => {
    positions.set(a.id, {
      x: 80 + i * 100,
      y: 60,
    });
  });

  return positions;
}

export interface GraphDiff {
  addedNodes: string[];
  removedNodes: string[];
  updatedNodes: string[];
  addedEdges: string[];
  removedEdges: string[];
}

export function diffGraphs(
  prev: GraphSnapshot | null,
  next: GraphSnapshot
): GraphDiff {
  const nodeIds = (g: GraphSnapshot) =>
    new Set([
      ...g.claims.map((c) => c.id),
      ...g.evidence.map((e) => e.id),
      ...g.assumptions.map((a) => a.id),
    ]);
  const edgeIds = (g: GraphSnapshot) => new Set(g.edges.map((e) => e.id));

  const prevNodes = prev ? nodeIds(prev) : new Set<string>();
  const nextNodes = nodeIds(next);
  const prevEdges = prev ? edgeIds(prev) : new Set<string>();
  const nextEdges = edgeIds(next);

  const addedNodes = [...nextNodes].filter((id) => !prevNodes.has(id));
  const removedNodes = [...prevNodes].filter((id) => !nextNodes.has(id));

  const prevClaimMap = new Map(prev?.claims.map((c) => [c.id, c]) ?? []);
  const updatedNodes = next.claims
    .filter((c) => {
      const p = prevClaimMap.get(c.id);
      return p && p.status !== c.status;
    })
    .map((c) => c.id);

  const addedEdges = [...nextEdges].filter((id) => !prevEdges.has(id));
  const removedEdges = [...prevEdges].filter((id) => !nextEdges.has(id));

  return {
    addedNodes,
    removedNodes,
    updatedNodes,
    addedEdges,
    removedEdges,
  };
}
