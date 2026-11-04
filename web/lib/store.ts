"use client";

import type { NexusState, Toast } from "./types";
import { NEXUS_URL } from "./urls";

export type Phase = "connecting" | "live" | "reconnecting" | "demo";

export interface StoreState {
  phase: Phase;
  data: NexusState | null;
  toasts: Toast[];
}

/** Root store: one SSE stream of full-state snapshots, committed throttled
 * at 10 Hz through useSyncExternalStore selectors. Demo replays the exact
 * same commit path. */
class NexusStore {
  private listeners = new Set<() => void>();
  private state: StoreState = { phase: "connecting", data: null, toasts: [] };

  private pending: NexusState | null = null;
  private flushTimer: number | null = null;

  private source: EventSource | null = null;
  private reconnectTimer: number | null = null;
  private backoffMs = 600;

  private demoOn = false;
  private demoGen = 0;

  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getState = (): StoreState => this.state;

  private emit(): void {
    for (const listener of this.listeners) listener();
  }

  private patch(partial: Partial<StoreState>): void {
    this.state = { ...this.state, ...partial };
    this.emit();
  }

  connect(): void {
    if (typeof window === "undefined" || this.demoOn || this.source) return;
    if (this.state.phase !== "connecting" && this.state.phase !== "reconnecting") {
      this.patch({ phase: "connecting" });
    }
    let source: EventSource;
    try {
      source = new EventSource(`${NEXUS_URL}/events`);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.source = source;
    source.onopen = () => {
      this.backoffMs = 600;
      if (!this.demoOn && this.state.phase !== "live") this.patch({ phase: "live" });
    };
    source.onmessage = (event: MessageEvent<string>) => {
      if (this.demoOn) return;
      let next: unknown;
      try {
        next = JSON.parse(event.data);
      } catch {
        return;
      }
      if (!next || typeof next !== "object") return;
      this.backoffMs = 600;
      if (this.state.phase !== "live") this.patch({ phase: "live" });
      this.commit(next as NexusState);
    };
    source.onerror = () => {
      this.teardownSource();
      if (!this.demoOn) this.patch({ phase: "reconnecting" });
      this.scheduleReconnect();
    };
  }

  private teardownSource(): void {
    this.source?.close();
    this.source = null;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer !== null || this.demoOn) return;
    const delay = Math.min(this.backoffMs, 8000) + Math.random() * 250;
    this.backoffMs = Math.min(this.backoffMs * 2, 8000);
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  /** Throttle: at most one commit per 100 ms (10 per second). */
  commit(next: NexusState): void {
    this.pending = next;
    if (this.flushTimer === null) {
      this.flushTimer = window.setTimeout(() => {
        this.flushTimer = null;
        this.flush();
      }, 100);
    }
  }

  private flush(): void {
    const next = this.pending;
    this.pending = null;
    if (!next) return;

    this.patch({ data: next });
  }

  private pushToastInner(toast: Toast): void {
    const toasts = [...this.state.toasts.filter((t) => t.id !== toast.id), toast].slice(-3);
    this.patch({ toasts });
    window.setTimeout(() => this.dismissToast(toast.id), 5200);
  }

  dismissToast = (id: string): void => {
    if (!this.state.toasts.some((t) => t.id === id)) return;
    this.patch({ toasts: this.state.toasts.filter((t) => t.id !== id) });
  };

  /** Push a one-off notice (e.g. composer 409/network errors). */
  pushToast = (toast: Omit<Toast, "id">): void => {
    const id = `notice-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
    this.pushToastInner({ ...toast, id });
  };

  startDemo(): void {
    if (typeof window === "undefined") return;
    this.demoOn = true;
    // Bumping the generation invalidates the previous replay's timers, so
    // Start in demo mode cleanly restarts the scripted run.
    const gen = ++this.demoGen;
    this.teardownSource();
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.patch({ phase: "demo", data: null });
    let mode: "cloud" | "hybrid" = "cloud";
    try {
      const requested = new URLSearchParams(window.location.search).get("mode");
      if (requested === "hybrid") mode = requested;
    } catch {
      /* URL parsing ought to work; fall back to cloud. */
    }
    void startDemoScript(
      (next) => {
        if (this.demoOn && gen === this.demoGen) this.commit(next);
      },
      () => !this.demoOn || gen !== this.demoGen,
      mode
    );
  }
}

export const store = new NexusStore();

/** The demo script lives in its own module to keep the store lean. */
async function startDemoScript(
  commit: (next: NexusState) => void,
  cancelled: () => boolean,
  mode: "cloud" | "hybrid"
): Promise<void> {
  const { runDemo } = await import("./demo");
  runDemo(commit, cancelled, mode);
}
