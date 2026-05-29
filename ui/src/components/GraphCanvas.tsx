import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D, { type ForceGraphMethods } from "react-force-graph-2d";
import type { GraphSnapshot } from "@/types/artifacts";
import { diffGraphs } from "@/data/graphLayout";
import { drawNodeLabel } from "@/data/canvasLabels";
import {
  linkEndpointId,
  neighborIds,
  snapshotToForceGraph,
  STATUS_COLORS,
  type ForceLink,
  type ForceNode,
} from "@/data/graphToForce";

interface GraphCanvasProps {
  graph: GraphSnapshot;
  prevGraph: GraphSnapshot | null;
  onNodeSelect: (nodeId: string) => void;
  selectedNodeId?: string | null;
}

export function GraphCanvas({
  graph,
  prevGraph,
  onNodeSelect,
  selectedNodeId,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<ForceGraphMethods<ForceNode, ForceLink> | undefined>(undefined);
  const [dims, setDims] = useState({ w: 640, h: 480 });
  const [hoverNode, setHoverNode] = useState<ForceNode | null>(null);
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null);
  const [showLabels, setShowLabels] = useState(true);

  const diff = useMemo(() => diffGraphs(prevGraph, graph), [prevGraph, graph]);
  const graphData = useMemo(
    () => snapshotToForceGraph(graph, diff),
    [graph, diff]
  );

  const highlightId = selectedNodeId ?? focusNodeId;
  const neighbors = useMemo(() => {
    if (!highlightId) return null;
    return neighborIds(highlightId, graphData.links);
  }, [highlightId, graphData.links]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const update = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width > 0 && height > 0) {
        setDims({ w: width, h: height });
      }
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const t = window.setTimeout(() => {
      fgRef.current?.zoomToFit(400, 48);
    }, 450);
    return () => window.clearTimeout(t);
  }, [graphData, dims.w, dims.h]);

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force("charge")?.strength(-180);
    fg.d3Force("link")?.distance((link: ForceLink) => {
      const s = linkEndpointId(link.source);
      const t = linkEndpointId(link.target);
      const sn = graphData.nodes.find((n) => n.id === s);
      const tn = graphData.nodes.find((n) => n.id === t);
      const len = (sn?.fullText.length ?? 0) + (tn?.fullText.length ?? 0);
      return 70 + Math.min(len * 0.35, 80);
    });
    fg.d3ReheatSimulation();
  }, [graphData]);

  const linkColor = useCallback(
    (link: ForceLink) => {
      if (!highlightId) return link.color;
      const s = linkEndpointId(link.source);
      const t = linkEndpointId(link.target);
      if (s === highlightId || t === highlightId) return link.color;
      if (neighbors?.has(s) && neighbors?.has(t)) return link.color;
      return "rgba(60, 50, 42, 0.15)";
    },
    [highlightId, neighbors]
  );

  const linkWidth = useCallback(
    (link: ForceLink) => {
      if (!highlightId) return link.isNew ? 2 : 1;
      const s = linkEndpointId(link.source);
      const t = linkEndpointId(link.target);
      if (s === highlightId || t === highlightId) return 2.5;
      return 0.6;
    },
    [highlightId]
  );

  const paintNode = useCallback(
    (node: ForceNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      const r = Math.sqrt(node.val) * (node.id === highlightId ? 5 : 4);
      const dimmed = highlightId && node.id !== highlightId && !neighbors?.has(node.id);

      ctx.beginPath();
      ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.fillStyle = dimmed ? "rgba(90, 75, 62, 0.4)" : node.color;
      ctx.fill();

      if (node.id === highlightId || node.isNew || node.isUpdated) {
        ctx.strokeStyle =
          node.id === highlightId
            ? "#f4e8d4"
            : node.isNew
              ? "#f4e8d4"
              : "#e85d3a";
        ctx.lineWidth = (node.id === highlightId ? 2 : 1.5) / globalScale;
        ctx.stroke();
      }

      if (node.isNew && !dimmed) {
        ctx.beginPath();
        ctx.arc(x, y, r + 3 / globalScale, 0, 2 * Math.PI);
        ctx.strokeStyle = "rgba(244, 232, 212, 0.5)";
        ctx.lineWidth = 1 / globalScale;
        ctx.stroke();
      }

      drawNodeLabel(ctx, node, x, y, r, globalScale, {
        dimmed: !!dimmed,
        highlighted: node.id === highlightId,
        showLabels,
      });
    },
    [highlightId, neighbors, showLabels]
  );

  const onNodeClick = useCallback(
    (node: ForceNode) => {
      setFocusNodeId(node.id);
      onNodeSelect(node.id);
      if (node.x != null && node.y != null) {
        fgRef.current?.centerAt(node.x, node.y, 400);
      }
      fgRef.current?.zoom(2.2, 400);
    },
    [onNodeSelect]
  );

  const onBackgroundClick = useCallback(() => {
    setFocusNodeId(null);
    fgRef.current?.zoomToFit(400, 48);
  }, []);

  const isEmpty = graphData.nodes.length === 0;

  return (
    <div className="graph-canvas" ref={containerRef}>
      {isEmpty ? (
        <div className="graph-empty">No claims in the graph yet.</div>
      ) : (
        <ForceGraph2D
          ref={fgRef}
          width={dims.w}
          height={dims.h}
          graphData={graphData}
          nodeId="id"
          nodeLabel={(n) =>
            `<div class="fg-tooltip"><strong>${n.kind}</strong>${n.status ? ` · ${n.status}` : ""}<br/>${escapeHtml(n.fullText)}</div>`
          }
          nodeCanvasObject={paintNode}
          nodePointerAreaPaint={(node, color, ctx) => {
            const r = Math.sqrt(node.val) * 6;
            ctx.fillStyle = color;
            ctx.beginPath();
            ctx.arc(node.x ?? 0, node.y ?? 0, r, 0, 2 * Math.PI);
            ctx.fill();
          }}
          linkColor={linkColor}
          linkWidth={linkWidth}
          linkDirectionalParticles={(link) => (link.isNew ? 2 : 0)}
          linkDirectionalParticleWidth={2}
          linkDirectionalParticleSpeed={0.006}
          onNodeClick={onNodeClick}
          onNodeHover={(n) => setHoverNode(n)}
          onBackgroundClick={onBackgroundClick}
          cooldownTicks={120}
          d3AlphaDecay={0.022}
          d3VelocityDecay={0.35}
          warmupTicks={80}
          enableNodeDrag
          enableZoomInteraction
          enablePanInteraction
          backgroundColor="rgba(18, 14, 11, 0.92)"
        />
      )}

      <div className="graph-legend">
        {Object.entries(STATUS_COLORS).map(([status, color]) => (
          <span key={status} className="graph-legend-item">
            <i style={{ background: color }} />
            {status}
          </span>
        ))}
        <span className="graph-legend-item">
          <i style={{ background: "#5a7a9a" }} />
          evidence
        </span>
      </div>

      {hoverNode && (
        <div className="graph-hover-card">
          <span className="graph-hover-kind">
            {hoverNode.kind}
            {hoverNode.status ? ` · ${hoverNode.status}` : ""}
          </span>
          <p>{hoverNode.fullText}</p>
        </div>
      )}

      <label className="graph-label-toggle">
        <input
          type="checkbox"
          checked={showLabels}
          onChange={(e) => setShowLabels(e.target.checked)}
        />
        Show argument labels
      </label>

      <div className="graph-hint">Drag nodes · scroll to zoom · click to focus</div>

      <style>{`
        .graph-canvas {
          position: relative;
          width: 100%;
          height: 100%;
          min-height: 420px;
          flex: 1;
          border-radius: var(--radius-md);
          overflow: hidden;
          border: 1px solid var(--mist);
        }
        .graph-empty {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
          min-height: 420px;
          color: var(--parchment-dim);
          font-style: italic;
        }
        .graph-legend {
          position: absolute;
          top: 8px;
          left: 8px;
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem 0.75rem;
          padding: 0.4rem 0.6rem;
          background: rgba(26, 20, 16, 0.85);
          border-radius: var(--radius-sm);
          font-size: 0.65rem;
          color: var(--parchment-dim);
          pointer-events: none;
          z-index: 2;
        }
        .graph-legend-item {
          display: flex;
          align-items: center;
          gap: 0.3rem;
        }
        .graph-legend-item i {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          display: inline-block;
        }
        .graph-hover-card {
          position: absolute;
          bottom: 36px;
          left: 8px;
          right: 8px;
          max-width: 360px;
          padding: 0.6rem 0.75rem;
          background: rgba(36, 28, 22, 0.95);
          border: 1px solid var(--brass-dim);
          border-radius: var(--radius-sm);
          pointer-events: none;
          z-index: 2;
        }
        .graph-hover-kind {
          font-size: 0.68rem;
          color: var(--brass);
          text-transform: uppercase;
          letter-spacing: 0.06em;
        }
        .graph-hover-card p {
          margin: 0.35rem 0 0;
          font-size: 0.78rem;
          line-height: 1.35;
          color: var(--parchment);
        }
        .graph-label-toggle {
          position: absolute;
          top: 8px;
          right: 8px;
          display: flex;
          align-items: center;
          gap: 0.35rem;
          font-size: 0.68rem;
          color: var(--parchment-dim);
          background: rgba(26, 20, 16, 0.85);
          padding: 0.35rem 0.5rem;
          border-radius: var(--radius-sm);
          cursor: pointer;
          z-index: 2;
        }
        .graph-label-toggle input { accent-color: var(--brass); }
        .graph-hint {
          position: absolute;
          bottom: 8px;
          right: 10px;
          font-size: 0.62rem;
          color: var(--parchment-dim);
          opacity: 0.7;
          pointer-events: none;
        }
        .fg-tooltip { max-width: 280px; font-size: 12px; line-height: 1.35; }
      `}</style>
    </div>
  );
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
