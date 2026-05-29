/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_RUNS_ROOT?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
