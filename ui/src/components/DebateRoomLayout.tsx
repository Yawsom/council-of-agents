import type { ReactNode } from "react";

interface DebateRoomLayoutProps {
  arbiter: ReactNode;
  observer: ReactNode;
  agentsLeft: ReactNode[];
  agentsRight: ReactNode[];
  graph: ReactNode;
}

export function DebateRoomLayout({
  arbiter,
  observer,
  agentsLeft,
  agentsRight,
  graph,
}: DebateRoomLayoutProps) {
  return (
    <div className="debate-room page-enter">
      <div className="debate-top">
        <div className="debate-arbiter-slot">{arbiter}</div>
        <div className="debate-observer-slot">{observer}</div>
      </div>
      <div className="debate-middle">
        <div className="debate-agents-left">{agentsLeft}</div>
        <div className="debate-graph-center">{graph}</div>
        <div className="debate-agents-right">{agentsRight}</div>
      </div>
      <style>{`
        .debate-room {
          flex: 1;
          display: flex;
          flex-direction: column;
          min-height: 0;
          padding: 1rem;
          gap: 0.75rem;
        }
        .debate-top {
          display: flex;
          justify-content: center;
          align-items: flex-start;
          gap: 2rem;
          flex-shrink: 0;
        }
        .debate-arbiter-slot { flex: 0 0 auto; }
        .debate-observer-slot { flex: 0 0 auto; }
        .debate-middle {
          flex: 1;
          display: grid;
          grid-template-columns: minmax(100px, 1fr) minmax(280px, 2.5fr) minmax(100px, 1fr);
          gap: 0.5rem;
          min-height: 0;
        }
        .debate-agents-left,
        .debate-agents-right {
          display: flex;
          flex-direction: column;
          justify-content: space-around;
          align-items: center;
          gap: 0.5rem;
        }
        .debate-graph-center {
          min-height: 420px;
          height: 100%;
          display: flex;
          flex-direction: column;
          position: relative;
        }
        @media (max-width: 768px) {
          .debate-middle {
            grid-template-columns: 1fr;
            grid-template-rows: auto 1fr auto;
          }
          .debate-agents-left, .debate-agents-right {
            flex-direction: row;
            flex-wrap: wrap;
            justify-content: center;
          }
        }
      `}</style>
    </div>
  );
}
