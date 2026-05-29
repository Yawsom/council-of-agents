import type { FileEntry, LoadedRun } from "@/types/artifacts";
import { entriesFromFileList, loadRunFromEntries } from "./RunLoader";

export interface LivePollerOptions {
  files: FileList;
  displayName: string;
  intervalMs?: number;
  onUpdate: (run: LoadedRun) => void;
  onError?: (err: Error) => void;
}

/**
 * Polls the same directory selection by re-reading File references.
 * Works when the user keeps a run folder open while council writes artifacts.
 */
export class LiveRunPoller {
  private timer: ReturnType<typeof setInterval> | null = null;
  private files: FileList;
  private displayName: string;
  private intervalMs: number;
  private onUpdate: (run: LoadedRun) => void;
  private onError?: (err: Error) => void;
  private lastSignature = "";

  constructor(opts: LivePollerOptions) {
    this.files = opts.files;
    this.displayName = opts.displayName;
    this.intervalMs = opts.intervalMs ?? 2500;
    this.onUpdate = opts.onUpdate;
    this.onError = opts.onError;
  }

  start(): void {
    void this.tick();
    this.timer = setInterval(() => void this.tick(), this.intervalMs);
  }

  stop(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  private fileSignature(): string {
    const parts: string[] = [];
    for (let i = 0; i < this.files.length; i++) {
      const f = this.files[i];
      const rel = (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name;
      parts.push(`${rel}:${f.size}:${f.lastModified}`);
    }
    return parts.sort().join("|");
  }

  private async tick(): Promise<void> {
    try {
      const signature = this.fileSignature();
      if (signature === this.lastSignature && this.lastSignature !== "") {
        return;
      }
      this.lastSignature = signature;
      const entries: Map<string, FileEntry> = entriesFromFileList(this.files);
      const run = await loadRunFromEntries(entries, this.displayName, "folder");
      this.onUpdate(run);
    } catch (e) {
      this.onError?.(e instanceof Error ? e : new Error(String(e)));
    }
  }
}
