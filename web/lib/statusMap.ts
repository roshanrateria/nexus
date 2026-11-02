import type { Tone } from "./types";

export interface StatusInfo {
  label: string;
  tone: Tone;
  pulse: boolean;
}

/** Map a backend run status to pill color + label. `outcome` (set on done)
 * can override the label. */
export function statusInfo(status: string, outcome: string): StatusInfo {
  if (!status) return { label: "Starting", tone: "dim", pulse: true };
  switch (status) {
    case "starting":
      return { label: "Starting", tone: "dim", pulse: true };
    case "running":
      return { label: "Running", tone: "run", pulse: true };
    case "reporting":
      return { label: "Reporting", tone: "violet", pulse: true };
    case "done": {
      if (outcome === "goal_achieved") return { label: "Goal achieved", tone: "ok", pulse: false };
      if (outcome === "cancelled") return { label: "Cancelled", tone: "warn", pulse: false };
      if (outcome === "error") return { label: "Error", tone: "bad", pulse: false };
      return { label: outcome || "Finished", tone: "ok", pulse: false };
    }
    case "error":
      return { label: "Error", tone: "bad", pulse: false };
    case "goal_achieved":
      return { label: "Goal achieved", tone: "ok", pulse: false };
    case "goal_unreachable":
      return { label: "Goal unreachable", tone: "bad", pulse: false };
    case "budget_exhausted":
      return { label: "Budget exhausted", tone: "warn", pulse: false };
    default:
      return { label: status, tone: "dim", pulse: false };
  }
}

export const TONE_COLOR: Record<Tone, string> = {
  ok: "var(--ok)",
  warn: "var(--warn)",
  bad: "var(--bad)",
  run: "var(--run)",
  violet: "var(--violet)",
  dim: "var(--dim)",
};
