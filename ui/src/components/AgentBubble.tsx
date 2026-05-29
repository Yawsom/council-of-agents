import { SpeechBubble } from "./SpeechBubble";

interface AgentBubbleProps {
  id: string;
  label: string;
  model?: string;
  teaser: string;
  role?: "agent" | "arbiter" | "observer";
  active?: boolean;
  selected?: boolean;
  onClick: () => void;
}

export function AgentBubble({
  id,
  label,
  model,
  teaser,
  role = "agent",
  active,
  selected,
  onClick,
}: AgentBubbleProps) {
  return (
    <button
      type="button"
      className={`agent-bubble role-${role} ${active ? "active" : ""} ${selected ? "selected" : ""}`}
      onClick={onClick}
      aria-label={`${label}: ${teaser}`}
      data-agent-id={id}
    >
      <SpeechBubble text={teaser} />
      <span className="agent-orb" />
      <span className="agent-label">{label}</span>
      {model && <span className="agent-model">{model.split("/").pop()}</span>}
      <style>{`
        .agent-bubble {
          position: relative;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.25rem;
          background: none;
          border: none;
          padding: 0.5rem;
          cursor: pointer;
          color: var(--parchment);
        }
        .agent-orb {
          width: 52px;
          height: 52px;
          border-radius: 50%;
          background: radial-gradient(circle at 35% 30%, rgba(244,232,212,0.5), rgba(201,162,39,0.35) 45%, rgba(26,20,16,0.9) 100%);
          border: 2px solid var(--brass-dim);
          transition: transform var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast);
        }
        .role-arbiter .agent-orb, .role-observer .agent-orb {
          width: 58px;
          height: 58px;
        }
        .role-arbiter .agent-orb {
          border-color: var(--ember);
          background: radial-gradient(circle at 35% 30%, rgba(232,93,58,0.4), rgba(201,162,39,0.25) 50%, rgba(26,20,16,0.95));
        }
        .role-observer .agent-orb {
          border-color: var(--sage);
          background: radial-gradient(circle at 35% 30%, rgba(107,143,113,0.45), rgba(201,162,39,0.2) 50%, rgba(26,20,16,0.95));
        }
        .agent-bubble:hover .agent-orb {
          transform: scale(1.06);
          border-color: var(--brass);
        }
        .agent-bubble.active .agent-orb {
          animation: pulseRing 2s ease infinite;
          border-color: var(--brass);
        }
        .agent-bubble.selected .agent-orb {
          box-shadow: var(--shadow-glow);
          border-color: var(--parchment);
        }
        .agent-label {
          font-family: var(--font-display);
          font-size: 0.85rem;
          font-weight: 600;
        }
        .agent-model {
          font-size: 0.65rem;
          color: var(--parchment-dim);
          max-width: 90px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      `}</style>
    </button>
  );
}
