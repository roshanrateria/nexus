import type {
  Bucket,
  Evidence,
  HistoryRecord,
  Ledger,
  LogEntry,
  NexusState,
  Phase,
  Step,
  VisitedSite,
} from "./types";
import type { StoreState } from "./store";
import { evidencesEqual, logsEqual, recordsEqual, shallowEqual, stepsEqual, stringsEqual } from "./equal";
import { hostOf } from "./urls";

export function selectPhase(s: StoreState): Phase {
  return s.phase;
}

export function selectData(s: StoreState): NexusState | null {
  return s.data;
}

export function selectHeader(s: StoreState) {
  const d = s.data;
  return {
    phase: s.phase,
    goal: d?.goal ?? "",
    runId: d?.run_id ?? "",
    status: d?.status ?? "",
    outcome: d?.outcome ?? "",
  };
}

export interface Stats {
  historyLen: number;
  planLen: number;
  sites: number;
  evidenceCount: number;
  escalations: number;
  costUsd: number | null;
}

/** Header/stat-strip metrics. Sites falls back to unique hosts from history
 * URLs when the backend does not track `visited`. */
export function selectStats(s: StoreState): Stats {
  const d = s.data;
  if (!d) return { historyLen: 0, planLen: 0, sites: 0, evidenceCount: 0, escalations: 0, costUsd: null };
  const visited = d.visited;
  const cost = d.ledger?.cost_usd;
  return {
    historyLen: d.history.length,
    planLen: d.plan.length,
    sites:
      visited?.length ??
      uniqueHosts([...d.history.map((r) => r.url), d.current?.url]).length,
    evidenceCount: d.evidences.length,
    escalations: d.ledger?.planner_calls ?? 0,
    costUsd: cost === null || cost === undefined || Number.isNaN(cost) ? null : cost,
  };
}

function uniqueHosts(urls: (string | undefined)[]): string[] {
  const set = new Set<string>();
  for (const url of urls) {
    const host = hostOf(url);
    if (host) set.add(host);
  }
  return [...set];
}

export function selectPrivacy(s: StoreState) {
  const d = s.data;
  // The hub seeds an empty ledger ({}) until the first snapshot arrives, so
  // every bucket read must survive undefined (a crash here kills hydration).
  const cloud: Partial<Bucket> = d?.ledger?.cloud ?? {};
  const open: Partial<Bucket> = d?.ledger?.open ?? {};
  return {
    mode: d?.mode,
    imagesOut: cloud.images_out ?? 0,
    share: d?.ledger?.open_token_share ?? 0,
    plannerCalls: d?.ledger?.planner_calls ?? 0,
    steps: d?.history.length ?? 0,
    cloudCalls: cloud.calls ?? 0,
    cloudTokens: (cloud.prompt_tokens ?? 0) + (cloud.completion_tokens ?? 0),
    cloudBytes: cloud.bytes_out ?? 0,
    openCalls: open.calls ?? 0,
    openTokens: (open.prompt_tokens ?? 0) + (open.completion_tokens ?? 0),
    openBytes: open.bytes_out ?? 0,
  };
}

export function selectTimeline(s: StoreState) {
  const d = s.data;
  return {
    history: d?.history ?? [],
    plan: d?.plan ?? [],
  };
}

export function selectEye(s: StoreState) {
  const c = s.data?.current;
  return {
    runId: s.data?.run_id ?? "",
    status: s.data?.status ?? "",
    shot: c?.shot,
    url: c?.url,
    title: c?.title,
    iteration: c?.iteration,
    lastAction: c?.last_action,
  };
}

export function selectLog(s: StoreState): LogEntry[] {
  return s.data?.log ?? [];
}

/** Last `n` log lines, oldest first — the ticker slices off the tail. */
export function selectTicker(s: StoreState): LogEntry[] {
  return s.data?.log.slice(-3) ?? [];
}

export function selectEvidences(s: StoreState): Evidence[] {
  return s.data?.evidences ?? [];
}

export function selectVisited(s: StoreState): VisitedSite[] {
  return s.data?.visited ?? [];
}

export function selectReport(s: StoreState) {
  const d = s.data;
  return {
    report: d?.report ?? "",
    reportPath: d?.report_path ?? "",
    status: d?.status ?? "",
  };
}

export function selectGoalString(s: StoreState): string {
  return s.data?.goal ?? "";
}

export function selectStatusString(s: StoreState): string {
  return s.data?.status ?? "";
}

export function selectRunId(s: StoreState): string {
  return s.data?.run_id ?? "";
}

export function selectToastState(s: StoreState) {
  return { toasts: s.toasts };
}

function objectKeyEqual<T>(a: T, b: T, keys: (keyof T)[]): boolean {
  for (const k of keys) {
    if (!Object.is(a[k], b[k])) return false;
  }
  return true;
}

export const headerEqual = (a: ReturnType<typeof selectHeader>, b: ReturnType<typeof selectHeader>) =>
  objectKeyEqual(a, b, ["phase", "goal", "runId", "status", "outcome"]);

export const statsEqual = (a: Stats, b: Stats): boolean =>
  a.historyLen === b.historyLen &&
  a.planLen === b.planLen &&
  a.sites === b.sites &&
  a.evidenceCount === b.evidenceCount &&
  a.escalations === b.escalations &&
  a.costUsd === b.costUsd;

export const privacyEqual = shallowEqual;

export const timelineEqual = (
  a: ReturnType<typeof selectTimeline>,
  b: ReturnType<typeof selectTimeline>
) => recordsEqual(a.history, b.history) && stepsEqual(a.plan, b.plan);

export const eyeEqual = (
  a: ReturnType<typeof selectEye>,
  b: ReturnType<typeof selectEye>
) => objectKeyEqual(a, b, ["runId", "status", "shot", "url", "title", "iteration", "lastAction"]);

export const logEqual = logsEqual;
export const tickerEqual = logsEqual;

export const evidenceListEqual = evidencesEqual;

/** Visited rows only change by push/bump; id (url) + visits is enough. */
export const visitedEqual = (a: VisitedSite[] | undefined, b: VisitedSite[] | undefined): boolean => {
  if (a === b) return true;
  if (!a || !b || a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i].url !== b[i].url || a[i].visits !== b[i].visits || a[i].title !== b[i].title) return false;
  }
  return true;
};

export const reportEqual = (
  a: ReturnType<typeof selectReport>,
  b: ReturnType<typeof selectReport>
) =>
  stringsEqual(a.report, b.report) &&
  stringsEqual(a.reportPath, b.reportPath) &&
  stringsEqual(a.status, b.status);

export interface TimelineItem {
  key: string;
  state: "done" | "failed" | "active" | "queued";
  instruction: string;
  expected: string;
  assessment?: string;
  verdict?: HistoryRecord["verdict"];
  evidences: number;
}

export function buildTimeline(history: HistoryRecord[], plan: Step[]): TimelineItem[] {
  const items: TimelineItem[] = history.map((r, i) => ({
    key: `h-${i}`,
    state: r.complete ? "done" : "failed",
    instruction: r.instruction,
    expected: r.expected_outcome,
    assessment: r.verdict === "done" ? undefined : r.assessment,
    verdict: r.complete ? undefined : r.verdict,
    evidences: r.evidences.length,
  }));
  // Replans reuse instructions; a plan step already answered by history must
  // not render twice. The active pointer is the first uncovered step — the
  // only rows that can be active are plan-derived, in plan order.
  const doneInstructions = new Set(history.map((r) => r.instruction));
  let activeAssigned = false;
  plan.forEach((p, i) => {
    if (doneInstructions.has(p.instruction)) return;
    items.push({
      key: `p-${i}`,
      state: activeAssigned ? "queued" : "active",
      instruction: p.instruction,
      expected: p.expected_outcome,
      evidences: 0,
    });
    activeAssigned = true;
  });
  return items;
}

export interface LedgerLike {
  ledger?: Ledger;
}
