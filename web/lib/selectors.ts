import type {
  Evidence,
  HistoryRecord,
  LogEntry,
  NexusState,
  Phase,
  Step,
} from "./types";
import type { StoreState } from "./store";
import { evidencesEqual, logsEqual, recordsEqual, shallowEqual, stepsEqual, stringsEqual } from "./equal";

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

export function selectPrivacy(s: StoreState) {
  const d = s.data;
  return {
    imagesOut: d?.ledger?.cloud.images_out ?? 0,
    share: d?.ledger?.open_token_share ?? 0,
    plannerCalls: d?.ledger?.planner_calls ?? 0,
    steps: d?.history.length ?? 0,
    cloudCalls: d?.ledger?.cloud.calls ?? 0,
    cloudTokens: (d?.ledger?.cloud.prompt_tokens ?? 0) + (d?.ledger?.cloud.completion_tokens ?? 0),
    cloudBytes: d?.ledger?.cloud.bytes_out ?? 0,
    openCalls: d?.ledger?.open.calls ?? 0,
    openTokens: (d?.ledger?.open.prompt_tokens ?? 0) + (d?.ledger?.open.completion_tokens ?? 0),
    openBytes: d?.ledger?.open.bytes_out ?? 0,
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

export function selectEvidences(s: StoreState): Evidence[] {
  return s.data?.evidences ?? [];
}

export function selectReport(s: StoreState) {
  const d = s.data;
  return {
    report: d?.report ?? "",
    reportPath: d?.report_path ?? "",
    status: d?.status ?? "",
  };
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

export const evidenceListEqual = evidencesEqual;

export const reportEqual = (
  a: ReturnType<typeof selectReport>,
  b: ReturnType<typeof selectReport>
) => stringsEqual(a.report, b.report) && stringsEqual(a.reportPath, b.reportPath);

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
  plan.forEach((p, i) =>
    items.push({
      key: `p-${i}`,
      state: i === 0 ? "active" : "queued",
      instruction: p.instruction,
      expected: p.expected_outcome,
      evidences: 0,
    })
  );
  return items;
}
