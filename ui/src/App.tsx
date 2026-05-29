import { NavLink, Outlet, useLocation } from "react-router-dom";
import { RunPicker } from "@/components/RunPicker";
import { TimelineScrubber } from "@/components/TimelineScrubber";
import { useRunSession } from "@/context/RunSessionContext";

export function App() {
  const { run, isLive } = useRunSession();
  const location = useLocation();

  const question =
    run?.config.prompt ??
    (run?.config.prompt_file ? `Prompt file: ${run.config.prompt_file}` : "");

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Council</h1>
        {question && <p className="question">{question}</p>}
        <nav className="nav-tabs">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
            Graph
          </NavLink>
          <NavLink to="/chat" className={({ isActive }) => (isActive ? "active" : "")}>
            Chat
          </NavLink>
        </nav>
        <RunPicker />
        {isLive && <span className="live-badge">LIVE</span>}
        <style>{`
          .live-badge {
            font-size: 0.65rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            color: var(--ember);
            border: 1px solid var(--ember);
            padding: 0.15rem 0.4rem;
            border-radius: 4px;
            animation: pulseRing 2s ease infinite;
          }
        `}</style>
      </header>
      <main className="app-main">
        <Outlet key={location.pathname} />
      </main>
      {run && <TimelineScrubber />}
    </div>
  );
}
