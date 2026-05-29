import { useRef, useState } from "react";
import { entriesFromFileList, loadFixtureRun, loadRunFromEntries } from "@/data/RunLoader";
import { useRunSession } from "@/context/RunSessionContext";

export function RunPicker() {
  const { setRun, startLivePoll, stopLivePoll, isLive, followLive, setFollowLive } =
    useRunSession();
  const inputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveFiles, setLiveFiles] = useState<FileList | null>(null);
  const [runName, setRunName] = useState("");

  const handleFiles = async (files: FileList, enableLive = false) => {
    setLoading(true);
    setError(null);
    try {
      const entries = entriesFromFileList(files);
      const first = files[0] as File & { webkitRelativePath?: string };
      const folderName =
        first?.webkitRelativePath?.split("/")[0] ?? "loaded_run";
      setRunName(folderName);
      const run = await loadRunFromEntries(entries, folderName, "folder");
      setRun(run);
      setLiveFiles(files);
      if (enableLive) {
        startLivePoll(files, folderName);
      } else {
        stopLivePoll();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const onFolderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files?.length) void handleFiles(files, false);
  };

  const onLoadFixture = async () => {
    setLoading(true);
    setError(null);
    try {
      const run = await loadFixtureRun();
      setRun(run);
      setRunName(run.name);
      stopLivePoll();
      setLiveFiles(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const toggleLive = () => {
    if (isLive) {
      stopLivePoll();
      return;
    }
    if (liveFiles) startLivePoll(liveFiles, runName);
  };

  return (
    <div className="run-picker">
      <input
        ref={inputRef}
        type="file"
        /* @ts-expect-error webkitdirectory */
        webkitdirectory=""
        directory=""
        multiple
        hidden
        onChange={onFolderChange}
      />
      <button type="button" className="btn btn-primary" onClick={() => inputRef.current?.click()}>
        Open run folder
      </button>
      <button type="button" className="btn" onClick={() => void onLoadFixture()} disabled={loading}>
        Load sample
      </button>
      {liveFiles && (
        <>
          <button type="button" className="btn" onClick={toggleLive}>
            {isLive ? "Stop live" : "Watch live"}
          </button>
          <label className="follow-live">
            <input
              type="checkbox"
              checked={followLive}
              onChange={(e) => setFollowLive(e.target.checked)}
            />
            Follow live
          </label>
        </>
      )}
      {loading && <span className="run-picker-status">Loading…</span>}
      {error && <span className="run-picker-error">{error}</span>}
      <style>{`
        .run-picker { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
        .run-picker-status { color: var(--parchment-dim); font-size: 0.8rem; }
        .run-picker-error { color: var(--ember); font-size: 0.8rem; }
        .follow-live { display: flex; align-items: center; gap: 0.35rem; font-size: 0.8rem; color: var(--parchment-dim); cursor: pointer; }
      `}</style>
    </div>
  );
}
