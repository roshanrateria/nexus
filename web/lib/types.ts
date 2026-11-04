export type LogKind = "plan" | "action" | "ok" | "error" | "failed" | "retry";

export interface Evidence {
  id: string;
  url: string;
  original_text: string;
  summarized: string;
  shot?: string;
}

export interface Step {
  instruction: string;
  expected_outcome: string;
}

export type Verdict = "done" | "retry" | "replan";

export interface HistoryRecord {
  instruction: string;
  expected_outcome: string;
  complete: boolean;
  verdict: Verdict;
  assessment: string;
  report: string;
  evidences: Evidence[];
  url: string;
  shot?: string;
}

export interface Bucket {
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  /** Meta prompt-cache hits (input_token_details), 0 or absent when none. */
  cached_tokens?: number;
  bytes_out: number;
  images_out: number;
}

export interface Ledger {
  cloud: Bucket;
  open: Bucket;
  by_role: Record<string, Bucket>;
  planner_calls: number;
  open_token_share: number;
  /** Billed Meta Model API spend (USD); null/absent means no billed calls yet. */
  cost_usd?: number;
}

export interface CurrentState {
  instruction?: string;
  iteration?: number;
  url?: string;
  title?: string;
  last_action?: string;
  report?: string;
  shot?: string;
}

export interface LogEntry {
  t: string;
  kind: LogKind;
  text: string;
}

/** One observed page, deduped by URL, newest visit first. Shaped by the
 * backend hub (`visited`), absent in older snapshots. */
export interface VisitedSite {
  url: string;
  host: string;
  title: string;
  visits: number;
  first_t: string;
  last_t: string;
}

export interface NexusState {
  goal: string;
  run_id: string;
  status: string;
  outcome: string;
  mode?: string;
  thought: string;
  plan: Step[];
  history: HistoryRecord[];
  evidences: Evidence[];
  current: CurrentState;
  log: LogEntry[];
  report: string;
  report_path: string;
  ledger?: Ledger;
  visited?: VisitedSite[];
}

/** Store-level (web only) connection / replay state. */
export type Phase = "connecting" | "live" | "reconnecting" | "demo";

export interface Toast {
  id: string;
  kind: "escalation" | "notice";
  title: string;
  detail: string;
}

export type Tone = "ok" | "warn" | "bad" | "run" | "violet" | "dim";
