/** Content-based comparators used by store selectors, so panels only
 * re-render when their slice of the full-state snapshot actually changed. */

export function shallowEqual(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  if (
    typeof a !== "object" ||
    typeof b !== "object" ||
    a === null ||
    b === null
  ) {
    return false;
  }
  const ka = Object.keys(a);
  const kb = Object.keys(b);
  if (ka.length !== kb.length) return false;
  for (const k of ka) {
    if (
      !Object.prototype.hasOwnProperty.call(b, k) ||
      !Object.is((a as Record<string, unknown>)[k], (b as Record<string, unknown>)[k])
    ) {
      return false;
    }
  }
  return true;
}

interface RecordLike {
  instruction: string;
  expected_outcome: string;
  complete: boolean;
  verdict: string;
  assessment: string;
  report: string;
  url: string;
  shot?: string;
  evidences: { id: string; url: string; original_text: string; summarized: string; shot?: string }[];
}

function recordEqual(a: RecordLike, b: RecordLike): boolean {
  const keys: (keyof RecordLike)[] = [
    "instruction",
    "expected_outcome",
    "complete",
    "verdict",
    "assessment",
    "report",
    "url",
    "shot",
  ];
  for (const k of keys) {
    if (a[k] !== b[k]) return false;
  }
  const ea = a.evidences;
  const eb = b.evidences;
  if (ea.length !== eb.length) return false;
  for (let i = 0; i < ea.length; i++) {
    const x = ea[i];
    const y = eb[i];
    if (
      x.id !== y.id ||
      x.url !== y.url ||
      x.original_text !== y.original_text ||
      x.summarized !== y.summarized ||
      x.shot !== y.shot
    ) {
      return false;
    }
  }
  return true;
}

export function recordsEqual(
  a: RecordLike[] | undefined,
  b: RecordLike[] | undefined
): boolean {
  if (a === b) return true;
  if (!a || !b || a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (!recordEqual(a[i], b[i])) return false;
  }
  return true;
}

export function stepsEqual(
  a: { instruction: string; expected_outcome: string }[] | undefined,
  b: { instruction: string; expected_outcome: string }[] | undefined
): boolean {
  if (a === b) return true;
  if (!a || !b || a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (
      a[i].instruction !== b[i].instruction ||
      a[i].expected_outcome !== b[i].expected_outcome
    ) {
      return false;
    }
  }
  return true;
}

/** The log only ever appends (and can trim its head); first+last text is a
 * cheap signature that catches both. */
export function logsEqual(
  a: { t: string; kind: string; text: string }[] | undefined,
  b: { t: string; kind: string; text: string }[] | undefined
): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  if (a.length !== b.length) return false;
  if (a.length === 0) return true;
  const lastA = a[a.length - 1];
  const lastB = b[b.length - 1];
  return (
    lastA.text === lastB.text &&
    lastA.kind === lastB.kind &&
    firstText(a) === firstText(b)
  );
}

function firstText(list: { text: string }[]): string {
  for (const entry of list) return entry.text;
  return "";
}

export function evidencesEqual(
  a: { id: string; original_text: string; summarized: string; shot?: string }[] | undefined,
  b: { id: string; original_text: string; summarized: string; shot?: string }[] | undefined
): boolean {
  if (a === b) return true;
  if (!a || !b || a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    const x = a[i];
    const y = b[i];
    if (
      x.id !== y.id ||
      x.original_text !== y.original_text ||
      x.summarized !== y.summarized ||
      x.shot !== y.shot
    ) {
      return false;
    }
  }
  return true;
}

export function stringsEqual(a: unknown, b: unknown): boolean {
  return a === b;
}
