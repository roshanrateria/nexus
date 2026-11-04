import type { NexusState } from "./types";

/** Store selectors + comparators for the force-graph stage; signatures are
 * deliberately coarse because nodes are merged incrementally (positions are
 * kept across rebuilds, so a re-render never disturbs the layout). */

export type GraphState = { data: NexusState | null };

export interface HistoryLite {
  instruction: string;
  complete: boolean;
  verdict: "done" | "retry" | "replan";
  evidences: { id: string; summarized: string }[];
}

export interface PlanLite {
  instruction: string;
}

export const selectGraphGoal = (s: GraphState): string => s.data?.goal ?? "";
export const selectGraphPlan = (s: GraphState): PlanLite[] =>
  (s.data?.plan ?? []).map((p) => ({ instruction: p.instruction }));

export function selectGraphHistory(s: GraphState): HistoryLite[] {
  return (s.data?.history ?? []).map((r) => ({
    instruction: r.instruction,
    complete: r.complete,
    verdict: r.verdict,
    evidences: r.evidences.map((e) => ({ id: e.id, summarized: e.summarized })),
  }));
}

export const equalGoals = (a: string, b: string): boolean => a === b;

export const equalSteps = (a: PlanLite[], b: PlanLite[]): boolean => {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i].instruction !== b[i].instruction) return false;
  }
  return true;
};

export const equalHistoryLite = (a: HistoryLite[], b: HistoryLite[]): boolean => {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    const x = a[i];
    const y = b[i];
    if (x.instruction !== y.instruction || x.complete !== y.complete || x.verdict !== y.verdict) return false;
    const ex = x.evidences;
    const ey = y.evidences;
    if (ex.length !== ey.length) return false;
    for (let j = 0; j < ex.length; j++) {
      if (ex[j].id !== ey[j].id || ex[j].summarized !== ey[j].summarized) return false;
    }
  }
  return true;
};

/** Evidence only ever appends within a run; length is the whole story for
 * count-style consumers. */
export const evidenceCountEqual = (a: unknown[], b: unknown[]): boolean =>
  a === b || a.length === b.length;
