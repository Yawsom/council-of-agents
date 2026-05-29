import { useRunSession } from "@/context/RunSessionContext";

export function TimelineScrubber() {
  const { run, stepIndex, setStepIndex } = useRunSession();
  if (!run?.steps.length) return null;

  return (
    <div className="timeline-scrubber">
      <input
        type="range"
        min={0}
        max={Math.max(0, run.steps.length - 1)}
        value={stepIndex}
        onChange={(e) => setStepIndex(Number(e.target.value))}
        className="timeline-slider"
      />
      <div className="timeline-steps">
        {run.steps.map((step, i) => (
          <button
            key={step.id}
            type="button"
            className={`timeline-step ${i === stepIndex ? "active" : ""}`}
            onClick={() => setStepIndex(i)}
          >
            {step.label}
          </button>
        ))}
      </div>
      <style>{`
        .timeline-scrubber {
          padding: 0.75rem 1.25rem;
          background: var(--bg-panel);
          border-top: 1px solid var(--mist);
          flex-shrink: 0;
        }
        .timeline-slider {
          width: 100%;
          margin-bottom: 0.5rem;
          accent-color: var(--brass);
        }
        .timeline-steps {
          display: flex;
          flex-wrap: wrap;
          gap: 0.35rem;
        }
        .timeline-step {
          padding: 0.25rem 0.6rem;
          font-size: 0.72rem;
          border-radius: var(--radius-sm);
          border: 1px solid transparent;
          background: var(--bg-elevated);
          color: var(--parchment-dim);
        }
        .timeline-step:hover { border-color: var(--brass-dim); color: var(--parchment); }
        .timeline-step.active {
          border-color: var(--brass);
          color: var(--brass);
          background: rgba(201, 162, 39, 0.12);
        }
      `}</style>
    </div>
  );
}
