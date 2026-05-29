# Council Debate Room UI

Experimental **read-only** viewer for council run artifacts. Zero coupling to the Python pipeline — it only reads JSON/YAML files the CLI already writes under `runs/`.

## Quick start

```bash
cd ui
npm install
npm run dev
```

Open http://localhost:5173 and click **Load sample** (bundled fixture) or **Open run folder** (select a `runs/YYYYMMDD_HHMMSS_name/` directory).

## Views

| View | Route | Description |
|------|-------|-------------|
| **Graph** | `/` | Debate room — agents as orbs with speech previews; **Obsidian-style force graph** in the center (draggable nodes, zoom/pan, neighbor highlight on click), arbiter top-center, observer top-right |
| **Chat** | `/chat` | Side-by-side transcript columns per agent (+ arbiter / observer) |

Use the **timeline scrubber** to step through Phase 1 → rounds → verdicts. The graph animates nodes/edges as snapshots change.

## Loading runs

### Folder picker (recommended)

1. Run the council CLI: `council run --mock` (or a live run).
2. In the UI, **Open run folder** and select the run directory (e.g. `runs/20260524_143022_my_run/`).
3. The browser reads all files client-side — nothing is uploaded.

### Bundled fixture

**Load sample** uses `fixtures/sample_run/` (toilet-paper deliberation demo, no API keys).

### Live watch (in-progress runs)

After opening a run folder:

1. Click **Watch live** — polls the same folder every ~2.5s as new snapshots/transcripts appear.
2. Enable **Follow live** to keep the scrubber on the latest step.

Works while `council run` is still writing artifacts. No Python changes required.

### Dev: serve local `runs/` (optional)

```bash
# From ui/
VITE_RUNS_ROOT=/runs npm run dev
```

Add a Vite middleware or copy runs into `ui/public/runs/` if you want fetch-based loading without the folder picker.

## Version B note

The UI always shows **true** graph snapshots from disk. In manipulation experiments, agents see a disguised graph in prompts — not what is rendered here.

## Evidence / rigour

The viewer displays agent-cited evidence as recorded in the graph. It does **not** verify sources; the observer audits structural consistency only (same as the CLI).

## Build

```bash
npm run build
npm run preview
```

Static output in `ui/dist/` — host anywhere; users still load runs via folder picker.

## Stack

- Vite + React + TypeScript
- React Router
- [react-force-graph-2d](https://github.com/vasturiano/react-force-graph) for the Obsidian-style claim graph
- `yaml` for `config.yaml` parsing

No dependency on `src/council`.
