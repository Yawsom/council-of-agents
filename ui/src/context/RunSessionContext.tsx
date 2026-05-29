import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { LoadedRun, TimelineStep } from "@/types/artifacts";
import { LiveRunPoller } from "@/data/LiveRunPoller";

interface RunSessionState {
  run: LoadedRun | null;
  stepIndex: number;
  selectedAgentId: string | null;
  selectedNodeId: string | null;
  followLive: boolean;
  isLive: boolean;
  setRun: (run: LoadedRun | null) => void;
  setStepIndex: (index: number) => void;
  setSelectedAgentId: (id: string | null) => void;
  setSelectedNodeId: (id: string | null) => void;
  setFollowLive: (v: boolean) => void;
  startLivePoll: (files: FileList, name: string) => void;
  stopLivePoll: () => void;
  currentStep: TimelineStep | null;
}

const RunSessionContext = createContext<RunSessionState | null>(null);

export function RunSessionProvider({ children }: { children: ReactNode }) {
  const [run, setRunState] = useState<LoadedRun | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [followLive, setFollowLive] = useState(false);
  const [poller, setPoller] = useState<LiveRunPoller | null>(null);
  const [isLive, setIsLive] = useState(false);
  const followLiveRef = useRef(followLive);
  useEffect(() => {
    followLiveRef.current = followLive;
  }, [followLive]);

  const setRun = useCallback(
    (r: LoadedRun | null) => {
      setRunState(r);
      setStepIndex(0);
      setSelectedAgentId(null);
      setSelectedNodeId(null);
    },
    []
  );

  const currentStep = run?.steps[stepIndex] ?? null;

  const startLivePoll = useCallback(
    (files: FileList, name: string) => {
      poller?.stop();
      const p = new LiveRunPoller({
        files,
        displayName: name,
        onUpdate: (updated) => {
          setRunState(updated);
          if (followLiveRef.current) {
            setStepIndex(Math.max(0, updated.steps.length - 1));
          }
        },
      });
      p.start();
      setPoller(p);
      setIsLive(true);
    },
    [poller]
  );

  const stopLivePoll = useCallback(() => {
    poller?.stop();
    setPoller(null);
    setIsLive(false);
  }, [poller]);

  const value = useMemo(
    () => ({
      run,
      stepIndex,
      selectedAgentId,
      selectedNodeId,
      followLive,
      isLive,
      setRun,
      setStepIndex,
      setSelectedAgentId,
      setSelectedNodeId,
      setFollowLive,
      startLivePoll,
      stopLivePoll,
      currentStep,
    }),
    [
      run,
      stepIndex,
      selectedAgentId,
      selectedNodeId,
      followLive,
      isLive,
      setRun,
      startLivePoll,
      stopLivePoll,
      currentStep,
    ]
  );

  return (
    <RunSessionContext.Provider value={value}>{children}</RunSessionContext.Provider>
  );
}

export function useRunSession(): RunSessionState {
  const ctx = useContext(RunSessionContext);
  if (!ctx) throw new Error("useRunSession must be used within RunSessionProvider");
  return ctx;
}
