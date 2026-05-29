import { FormattedCard } from "@/components/chat/FormattedCard";
import {
  formatAgentTranscript,
  formatArbiter,
  formatObserver,
  formatVerdict,
  shortAgentId,
} from "@/data/formatTranscript";
import { useRunSession } from "@/context/RunSessionContext";
import type { TimelineStep } from "@/types/artifacts";

function graphForStep(steps: TimelineStep[], index: number) {
  return steps[Math.min(index, steps.length - 1)]?.graph ?? null;
}

export function ChatView() {
  const { run, stepIndex, currentStep } = useRunSession();

  if (!run || !currentStep) {
    return (
      <div className="empty-state">
        <h2>Transcript hall</h2>
        <p>Load a run to read each agent side by side.</p>
      </div>
    );
  }

  const agents = run.config.agents;

  return (
    <div className="chat-view page-enter">
      <p className="chat-intro">
        Readable summaries through <strong>{currentStep.label}</strong> — scrub the timeline to
        reveal later rounds.
      </p>
      <div className="chat-columns">
        {agents.map((a) => (
          <section key={a.id} className="chat-column">
            <header className="chat-column-head">
              <h3>{shortAgentId(a.id)}</h3>
              <span className="chat-model">{a.model.split("/").pop()}</span>
            </header>
            <div className="chat-scroll">
              {run.steps.slice(0, stepIndex + 1).map((step, i) => {
                if (step.phase === "verdicts") {
                  const v = step.verdicts?.find((x) => x.agent_id === a.id);
                  if (!v) return null;
                  return (
                    <FormattedCard
                      key={`${a.id}-verdict`}
                      stepLabel="Final verdict"
                      sections={formatVerdict(v, step.graph)}
                    />
                  );
                }
                const t = step.agentTranscripts[a.id];
                if (!t) return null;
                return (
                  <FormattedCard
                    key={`${a.id}-${step.id}`}
                    stepLabel={step.label}
                    sections={formatAgentTranscript(t, graphForStep(run.steps, i))}
                  />
                );
              })}
              {run.steps.slice(0, stepIndex + 1).every(
                (s) =>
                  s.phase !== "verdicts" || !s.verdicts?.some((v) => v.agent_id === a.id)
              ) &&
                !run.steps
                  .slice(0, stepIndex + 1)
                  .some((s) => s.agentTranscripts[a.id]) && (
                  <p className="chat-empty">Silent so far.</p>
                )}
            </div>
          </section>
        ))}

        <section className="chat-column chat-column-role">
          <header className="chat-column-head">
            <h3>Arbiter</h3>
            <span className="chat-model">provocateur</span>
          </header>
          <div className="chat-scroll">
            {run.steps.slice(0, stepIndex + 1).map((step, i) =>
              step.arbiter ? (
                <FormattedCard
                  key={`arb-${step.id}`}
                  stepLabel={step.label}
                  sections={formatArbiter(step.arbiter, graphForStep(run.steps, i))}
                />
              ) : null
            )}
          </div>
        </section>

        <section className="chat-column chat-column-role">
          <header className="chat-column-head">
            <h3>Observer</h3>
            <span className="chat-model">auditor</span>
          </header>
          <div className="chat-scroll">
            {run.steps.slice(0, stepIndex + 1).map((step) =>
              step.observer?.length ? (
                <FormattedCard
                  key={`obs-${step.id}`}
                  stepLabel={step.label}
                  sections={formatObserver(step.observer)}
                />
              ) : null
            )}
          </div>
        </section>
      </div>

      <style>{`
        .chat-view {
          flex: 1;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          padding: 1rem;
          min-height: 0;
        }
        .chat-intro {
          margin: 0 0 0.75rem;
          font-size: 0.8rem;
          color: var(--parchment-dim);
        }
        .chat-columns {
          display: flex;
          gap: 0.75rem;
          overflow-x: auto;
          flex: 1;
          min-height: 0;
          align-items: stretch;
        }
        .chat-column {
          flex: 0 0 300px;
          display: flex;
          flex-direction: column;
          background: var(--bg-panel);
          border-radius: var(--radius-md);
          border: 1px solid var(--mist);
          min-height: 0;
        }
        .chat-column-head {
          padding: 0.75rem 0.75rem 0.5rem;
          border-bottom: 1px solid var(--mist);
        }
        .chat-column-head h3 {
          margin: 0;
          font-family: var(--font-display);
          font-size: 1.1rem;
          color: var(--parchment);
        }
        .chat-model {
          font-size: 0.68rem;
          color: var(--parchment-dim);
        }
        .chat-scroll {
          flex: 1;
          overflow-y: auto;
          padding: 0.5rem;
          display: flex;
          flex-direction: column;
          gap: 0.6rem;
        }
        .chat-empty {
          color: var(--parchment-dim);
          font-size: 0.8rem;
          padding: 0.5rem;
          font-style: italic;
        }
        .chat-column-role { flex: 0 0 260px; }

        .fmt-card {
          background: var(--bg-deep);
          border-radius: var(--radius-sm);
          border: 1px solid rgba(201, 162, 39, 0.12);
          overflow: hidden;
        }
        .fmt-card-header {
          padding: 0.4rem 0.6rem;
          font-size: 0.7rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--brass);
          background: rgba(201, 162, 39, 0.08);
          border-bottom: 1px solid var(--mist);
        }
        .fmt-card-body { padding: 0.5rem 0.6rem; }
        .fmt-section + .fmt-section { margin-top: 0.6rem; }
        .fmt-heading {
          margin: 0 0 0.35rem;
          font-size: 0.72rem;
          font-weight: 600;
          color: var(--parchment-dim);
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
        .fmt-list {
          list-style: none;
          margin: 0;
          padding: 0;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }
        .fmt-item { position: relative; padding-left: 0; }
        .fmt-tag {
          display: inline-block;
          font-size: 0.58rem;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          color: var(--brass);
          margin-bottom: 0.2rem;
        }
        .fmt-text {
          margin: 0;
          font-size: 0.82rem;
          line-height: 1.45;
          color: var(--parchment);
        }
        .fmt-meta {
          margin: 0.25rem 0 0;
          font-size: 0.72rem;
          line-height: 1.35;
          color: var(--parchment-dim);
          font-style: italic;
        }
        .fmt-tone-negative .fmt-text { color: #e8a090; }
        .fmt-tone-positive .fmt-text { color: #a8c9ab; }
        .fmt-tone-warn .fmt-text { color: #e8c47a; }
        .fmt-badge {
          display: inline-block;
          padding: 0.2rem 0.45rem;
          border-radius: 4px;
          font-size: 0.75rem;
          font-weight: 500;
        }
        .fmt-badge-neutral { background: var(--bg-elevated); color: var(--parchment); }
        .fmt-badge-positive { background: rgba(107, 143, 113, 0.25); color: #a8c9ab; }
        .fmt-badge-negative { background: rgba(232, 93, 58, 0.2); color: #e8a090; }
        .fmt-badge-warn { background: rgba(201, 162, 39, 0.2); color: var(--brass); }
      `}</style>
    </div>
  );
}
