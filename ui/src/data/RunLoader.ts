import { parse as parseYaml } from "yaml";
import type {
  ArbiterOutput,
  FileEntry,
  GraphSnapshot,
  LoadedRun,
  ObserverCheck,
  Phase1Transcript,
  Phase2Transcript,
  RunConfig,
  Verdict,
} from "@/types/artifacts";
import { buildTimeline } from "./TimelineBuilder";

function parseJson<T>(text: string): T {
  return JSON.parse(text) as T;
}

async function readOptional<T>(entries: Map<string, FileEntry>, path: string): Promise<T | undefined> {
  const entry = entries.get(path);
  if (!entry) return undefined;
  try {
    return parseJson<T>(await entry.getText());
  } catch {
    return undefined;
  }
}

function normalizePath(p: string): string {
  return p.replace(/\\/g, "/").replace(/^\/+/, "");
}

/** Build file map from directory picker (webkitdirectory). */
export function entriesFromFileList(files: FileList): Map<string, FileEntry> {
  const map = new Map<string, FileEntry>();
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const rel = normalizePath((file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name);
    const parts = rel.split("/");
    const path = parts.length > 1 ? parts.slice(1).join("/") : rel;
    map.set(path, {
      path,
      name: file.name,
      getText: () => file.text(),
    });
  }
  return map;
}

/** Load run from a flat map of relative paths → file content. */
export async function loadRunFromEntries(
  entries: Map<string, FileEntry>,
  displayName: string,
  source: LoadedRun["source"] = "folder"
): Promise<LoadedRun> {
  const configText =
    (await entries.get("config.yaml")?.getText()) ??
    (await entries.get("./config.yaml")?.getText());
  if (!configText) {
    throw new Error("Missing config.yaml in run folder");
  }

  const config = parseYaml(configText) as RunConfig;
  if (!config.agents?.length) {
    config.agents = inferAgentsFromTranscripts(entries);
  }

  const snapshots = new Map<string, GraphSnapshot>();
  for (const [path, entry] of entries) {
    if (path.startsWith("graph_snapshots/") && path.endsWith(".json")) {
      const label = path.replace("graph_snapshots/", "").replace(".json", "");
      snapshots.set(label, parseJson<GraphSnapshot>(await entry.getText()));
    }
  }

  let finalGraph = await readOptional<GraphSnapshot>(entries, "final_graph.json");
  if (!finalGraph && snapshots.size > 0) {
    const roundKeys = [...snapshots.keys()].filter((k) => k.startsWith("round_"));
    roundKeys.sort((a, b) => parseInt(a.replace("round_", ""), 10) - parseInt(b.replace("round_", ""), 10));
    const last = roundKeys[roundKeys.length - 1] ?? "phase1";
    finalGraph = snapshots.get(last)!;
  }

  const phase1Transcripts: Record<string, Phase1Transcript> = {};
  for (const [path, entry] of entries) {
    const m = path.match(/^transcripts\/phase1\/(.+)_output\.json$/);
    if (m) {
      const raw = parseJson<Phase1Transcript>(await entry.getText());
      phase1Transcripts[raw.agent_id ?? m[1]] = raw;
    }
  }

  const roundNumbers = new Set<number>();
  for (const path of entries.keys()) {
    const m = path.match(/^transcripts\/round_(\d+)\//);
    if (m) roundNumbers.add(parseInt(m[1], 10));
  }

  const rounds: Array<{
    round: number;
    agents: Record<string, Phase2Transcript>;
    arbiter?: ArbiterOutput;
    observer?: ObserverCheck[];
    graph?: GraphSnapshot;
  }> = [];

  for (const r of [...roundNumbers].sort((a, b) => a - b)) {
    const agents: Record<string, Phase2Transcript> = {};
    for (const [path, entry] of entries) {
      const am = path.match(new RegExp(`^transcripts/round_${r}/(.+)_output\\.json$`));
      if (am) {
        const raw = parseJson<Phase2Transcript>(await entry.getText());
        agents[raw.agent_id ?? am[1]] = raw;
      }
    }
    const arbiter = await readOptional<ArbiterOutput>(entries, `transcripts/round_${r}/arbiter_output.json`);
    const observer = await readOptional<ObserverCheck[]>(entries, `transcripts/round_${r}/observer_checks.json`);
    const graph = snapshots.get(`round_${r}`);
    rounds.push({ round: r, agents, arbiter, observer, graph });
  }

  const verdicts = await readOptional<Verdict[]>(entries, "verdicts.json");

  const steps = buildTimeline({
    phase1Graph: snapshots.get("phase1"),
    phase1Transcripts,
    rounds,
    finalGraph: finalGraph ?? { claims: [], evidence: [], assumptions: [], edges: [] },
    verdicts,
  });

  return {
    name: displayName,
    config,
    steps,
    source,
  };
}

function inferAgentsFromTranscripts(entries: Map<string, FileEntry>): RunConfig["agents"] {
  const ids = new Set<string>();
  for (const path of entries.keys()) {
    const m = path.match(/transcripts\/(?:phase1|round_\d+)\/(.+)_output\.json/);
    if (m && !m[1].includes("arbiter")) {
      ids.add(m[1]);
    }
  }
  return [...ids].map((id) => ({ id, model: "unknown" }));
}

/** Fetch run from dev server path (VITE_RUNS_ROOT). */
export async function loadRunFromDevPath(runFolderName: string): Promise<LoadedRun> {
  const root = import.meta.env.VITE_RUNS_ROOT ?? "/runs";
  const base = `${root}/${runFolderName}`.replace(/\/+/g, "/");

  async function fetchText(path: string): Promise<string | null> {
    try {
      const res = await fetch(`${base}/${path}`);
      if (!res.ok) return null;
      return res.text();
    } catch {
      return null;
    }
  }

  const manifest = [
    "config.yaml",
    "final_graph.json",
    "verdicts.json",
    "graph_snapshots/phase1.json",
  ];

  const entries = new Map<string, FileEntry>();

  const configText = await fetchText("config.yaml");
  if (!configText) throw new Error(`Cannot load run at ${base}`);

  const add = (path: string, text: string) => {
    entries.set(path, {
      path,
      name: path.split("/").pop() ?? path,
      getText: async () => text,
    });
  };

  add("config.yaml", configText);

  for (const p of manifest) {
    const t = await fetchText(p);
    if (t) add(p, t);
  }

  for (let r = 1; r <= 20; r++) {
    const snap = await fetchText(`graph_snapshots/round_${r}.json`);
    if (snap) add(`graph_snapshots/round_${r}.json`, snap);
    else if (r > 1) break;

    const phase1Agents = await listDevAgents(base, `transcripts/round_${r}`);
    for (const agent of phase1Agents) {
      const t = await fetchText(`transcripts/round_${r}/${agent}_output.json`);
      if (t) add(`transcripts/round_${r}/${agent}_output.json`, t);
    }
    const arb = await fetchText(`transcripts/round_${r}/arbiter_output.json`);
    if (arb) add(`transcripts/round_${r}/arbiter_output.json`, arb);
    const obs = await fetchText(`transcripts/round_${r}/observer_checks.json`);
    if (obs) add(`transcripts/round_${r}/observer_checks.json`, obs);
  }

  const p1 = await fetchText("graph_snapshots/phase1.json");
  if (p1) add("graph_snapshots/phase1.json", p1);

  const agents = await listDevAgents(base, "transcripts/phase1");
  for (const agent of agents) {
    const t = await fetchText(`transcripts/phase1/${agent}_output.json`);
    if (t) add(`transcripts/phase1/${agent}_output.json`, t);
  }

  const fg = await fetchText("final_graph.json");
  if (fg) add("final_graph.json", fg);
  const v = await fetchText("verdicts.json");
  if (v) add("verdicts.json", v);

  return loadRunFromEntries(entries, runFolderName, "dev");
}

async function listDevAgents(_base: string, _prefix: string): Promise<string[]> {
  return [];
}

/** Load bundled fixture (for dev/demo without local runs). */
export async function loadFixtureRun(): Promise<LoadedRun> {
  const modules = import.meta.glob("../../fixtures/sample_run/**/*.{json,yaml}", {
    query: "?raw",
    import: "default",
    eager: true,
  }) as Record<string, string>;

  const entries = new Map<string, FileEntry>();
  for (const [fullPath, content] of Object.entries(modules)) {
    const marker = "fixtures/sample_run/";
    const idx = fullPath.indexOf(marker);
    const path = idx >= 0 ? fullPath.slice(idx + marker.length) : fullPath;
    entries.set(path, {
      path,
      name: path.split("/").pop() ?? path,
      getText: async () => content,
    });
  }

  return loadRunFromEntries(entries, "sample_run (fixture)", "fixture");
}
