import { useMemo } from "react";
import { AgentBubble } from "@/components/AgentBubble";
import { AgentDetailDrawer } from "@/components/AgentDetailDrawer";
import { DebateRoomLayout } from "@/components/DebateRoomLayout";
import { GraphCanvas } from "@/components/GraphCanvas";
import {
  agentTeaser,
  arbiterTeaser,
  observerTeaser,
  verdictTeaser,
} from "@/data/speechTeaser";
import { useRunSession } from "@/context/RunSessionContext";

function shortId(id: string): string {
  return id.replace(/^agent_/, "").replace(/_/g, " ");
}

export function GraphView() {
  const {
    run,
    stepIndex,
    currentStep,
    selectedAgentId,
    selectedNodeId,
    setSelectedAgentId,
    setSelectedNodeId,
  } = useRunSession();

  const prevGraph = useMemo(() => {
    if (!run || stepIndex <= 0) return null;
    return run.steps[stepIndex - 1]?.graph ?? null;
  }, [run, stepIndex]);

  if (!run || !currentStep) {
    return (
      <div className="empty-state">
        <h2>Chamber of Deliberation</h2>
        <p>Open a council run folder to enter the debate room.</p>
      </div>
    );
  }

  const agents = run.config.agents;
  const mid = Math.ceil(agents.length / 2);
  const left = agents.slice(0, mid);
  const right = agents.slice(mid);

  const renderAgent = (a: (typeof agents)[0]) => {
    const transcript = currentStep.agentTranscripts[a.id];
    const verdict = currentStep.verdicts?.find((v) => v.agent_id === a.id);
    const teaser =
      currentStep.phase === "verdicts"
        ? verdictTeaser(verdict)
        : agentTeaser(transcript);
    return (
      <AgentBubble
        key={a.id}
        id={a.id}
        label={shortId(a.id)}
        model={a.model}
        teaser={teaser}
        active={!!transcript || !!verdict}
        selected={selectedAgentId === a.id}
        onClick={() => {
          setSelectedNodeId(null);
          setSelectedAgentId(a.id);
        }}
      />
    );
  };

  return (
    <>
      <DebateRoomLayout
        arbiter={
          <AgentBubble
            id="arbiter"
            label="Arbiter"
            model={run.config.arbiter_model}
            teaser={arbiterTeaser(currentStep.arbiter)}
            role="arbiter"
            active={!!currentStep.arbiter}
            selected={selectedAgentId === "arbiter"}
            onClick={() => {
              setSelectedNodeId(null);
              setSelectedAgentId("arbiter");
            }}
          />
        }
        observer={
          <AgentBubble
            id="observer"
            label="Observer"
            model={run.config.observer_model}
            teaser={observerTeaser(currentStep.observer)}
            role="observer"
            active={!!currentStep.observer?.length}
            selected={selectedAgentId === "observer"}
            onClick={() => {
              setSelectedNodeId(null);
              setSelectedAgentId("observer");
            }}
          />
        }
        agentsLeft={left.map(renderAgent)}
        agentsRight={right.map(renderAgent)}
        graph={
          <GraphCanvas
            graph={currentStep.graph}
            prevGraph={prevGraph}
            selectedNodeId={selectedNodeId}
            onNodeSelect={(id) => {
              setSelectedAgentId(null);
              setSelectedNodeId(id);
            }}
          />
        }
      />
      <AgentDetailDrawer />
    </>
  );
}
