import { useRunSession } from "@/context/RunSessionContext";
import type { GraphSnapshot } from "@/types/artifacts";

function findNode(graph: GraphSnapshot, id: string) {
  const claim = graph.claims.find((c) => c.id === id);
  if (claim) return { kind: "claim" as const, data: claim };
  const ev = graph.evidence.find((e) => e.id === id);
  if (ev) return { kind: "evidence" as const, data: ev };
  const a = graph.assumptions.find((x) => x.id === id);
  if (a) return { kind: "assumption" as const, data: a };
  return null;
}

export function AgentDetailDrawer() {
  const {
    run,
    currentStep,
    selectedAgentId,
    selectedNodeId,
    setSelectedAgentId,
    setSelectedNodeId,
  } = useRunSession();

  const open = selectedAgentId !== null || selectedNodeId !== null;
  if (!open || !currentStep) return null;

  const close = () => {
    setSelectedAgentId(null);
    setSelectedNodeId(null);
  };

  let title = "";
  let body: React.ReactNode = null;

  if (selectedNodeId && run) {
    const node = findNode(currentStep.graph, selectedNodeId);
    title = selectedNodeId;
    body = node ? (
      <pre className="json-block">{JSON.stringify(node.data, null, 2)}</pre>
    ) : (
      <p>Node not found in current graph.</p>
    );
  } else if (selectedAgentId) {
    title = selectedAgentId;
    if (selectedAgentId === "arbiter") {
      body = currentStep.arbiter ? (
        <pre className="json-block">{JSON.stringify(currentStep.arbiter, null, 2)}</pre>
      ) : (
        <p>Arbiter silent at this step.</p>
      );
    } else if (selectedAgentId === "observer") {
      body = currentStep.observer?.length ? (
        <pre className="json-block">{JSON.stringify(currentStep.observer, null, 2)}</pre>
      ) : (
        <p>Observer silent at this step.</p>
      );
    } else if (currentStep.phase === "verdicts") {
      const v = currentStep.verdicts?.find((x) => x.agent_id === selectedAgentId);
      body = v ? (
        <pre className="json-block">{JSON.stringify(v, null, 2)}</pre>
      ) : (
        <p>No verdict for this agent.</p>
      );
    } else {
      const t = currentStep.agentTranscripts[selectedAgentId];
      body = t ? (
        <pre className="json-block">{JSON.stringify(t, null, 2)}</pre>
      ) : (
        <p>No transcript for this step.</p>
      );
    }
  }

  return (
    <>
      <div className="drawer-overlay" onClick={close} aria-hidden />
      <aside className="drawer-panel" role="dialog" aria-label="Detail">
        <button type="button" className="btn btn-ghost drawer-close" onClick={close}>
          Close
        </button>
        <h3>{title}</h3>
        {body}
      </aside>
    </>
  );
}
