/** Run-control API for the composer: start and cancel runs the same way the
 * CLI does, against the single-process runner (same origin by default). */

import { NEXUS_URL } from "./urls";

export type RunApiErrorKind = "bad_request" | "busy" | "network";

/** Typed failure for 400 / 409 / network errors — the composer renders a
 * toast per kind and keeps the goal text for a retry. */
export class RunApiError extends Error {
  constructor(
    readonly kind: RunApiErrorKind,
    message: string,
    readonly status = 0
  ) {
    super(message);
    this.name = "RunApiError";
  }
}

interface RunPayload {
  run_id?: string;
  error?: string;
}

async function readPayload(response: Response): Promise<RunPayload> {
  try {
    return (await response.json()) as RunPayload;
  } catch {
    return {};
  }
}

async function request(path: string, body?: string): Promise<Response> {
  try {
    return await fetch(`${NEXUS_URL}${path}`, {
      method: "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body,
    });
  } catch {
    throw new RunApiError("network", "Could not reach the agent — is runner.py running?");
  }
}

/** POST /run. Resolves with the queued run_id; throws on 400/409/network. */
export async function startRun(goal: string): Promise<string> {
  const response = await request("/run", JSON.stringify({ goal }));
  if (response.status === 409) {
    throw new RunApiError("busy", "Agent is busy — wait for the current run or cancel it.", 409);
  }
  const payload = await readPayload(response);
  if (!response.ok) {
    throw new RunApiError("bad_request", payload.error || `Request failed (${response.status})`, response.status);
  }
  if (typeof payload.run_id !== "string" || !payload.run_id) {
    throw new RunApiError("bad_request", "Malformed response from /run.", response.status);
  }
  return payload.run_id;
}

/** POST /cancel. Throws on 409 (idle) / network. */
export async function cancelRun(): Promise<void> {
  const response = await request("/cancel");
  if (response.status === 409) {
    throw new RunApiError("busy", "Nothing to cancel — the agent is idle.", 409);
  }
  if (!response.ok) {
    const payload = await readPayload(response);
    throw new RunApiError("bad_request", payload.error || `Cancel failed (${response.status})`, response.status);
  }
}
