"use client";

import { memo, useEffect, useRef, useState, type CSSProperties } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Plus, Square } from "lucide-react";
import { headerEqual, selectHeader } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { cancelRun, RunApiError } from "@/lib/api";
import { statusInfo } from "@/lib/statusMap";
import { fmtElapsed } from "@/lib/format";
import { SPRING, useEnter } from "@/lib/motion";
import { store } from "@/lib/store";
import { cn } from "@/lib/cn";
import { LogoGlyph, StatusPill } from "./ui";
import { ThemeToggle } from "./ThemeToggle";
import { ComposerSheet } from "./ComposerSheet";
import { MissionComposer } from "./MissionComposer";

const RUNNING = new Set(["running", "reporting"]);

function HeaderBase() {
  const state = useNexus(selectHeader, headerEqual);
  const info = statusInfo(state.status, state.outcome);
  const enter = useEnter(SPRING);
  const running = RUNNING.has(state.status);
  const finished = Boolean(state.status) && !running;
  const [goalOpen, setGoalOpen] = useState(false);

  // Click-away closes the expanded goal.
  useEffect(() => {
    if (!goalOpen) return;
    const onDown = (e: PointerEvent): void => {
      const target = e.target as HTMLElement | null;
      if (!target?.closest(".goal-pill") && !target?.closest("[role='dialog']")) setGoalOpen(false);
    };
    window.addEventListener("pointerdown", onDown);
    return () => window.removeEventListener("pointerdown", onDown);
  }, [goalOpen]);

  return (
    <header className="glass col-span-full flex flex-row items-center gap-3 rounded-[24px] px-4">
      <div className="flex shrink-0 items-center gap-2.5">
        <LogoGlyph size={30} />
        <div className="hidden flex-col leading-none sm:flex">
          <span className="text-[14px] font-semibold tracking-[0.05em]">NEXUS</span>
          <span className="caption mt-0.5 text-[9px]!">agentic browser</span>
        </div>
      </div>

      {/* goal pill: click to expand the full goal */}
      <div className="relative flex min-w-0 flex-1 justify-start">
        <button
          type="button"
          className="goal-pill"
          disabled={!state.goal}
          onClick={() => setGoalOpen((v) => !v)}
          aria-expanded={goalOpen}
          aria-haspopup="dialog"
          title={state.goal ? "Show the full goal" : "No goal yet"}
        >
          {state.goal ? (
            <>
              <span className="caption shrink-0 text-[10px]!">goal</span>
              <span className="truncate text-[12.5px] font-medium text-(--text)">{state.goal}</span>
            </>
          ) : (
            <span className="text-[12.5px] text-(--faint)">waiting for a goal…</span>
          )}
          {state.goal && <ChevronDown size={12} className={cn("shrink-0 transition-transform", goalOpen && "rotate-180")} />}
        </button>
        <AnimatePresence>
          {goalOpen && state.goal && (
            <motion.div
              role="dialog"
              aria-label="Full goal"
              initial={{ opacity: 0, y: -6, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.98 }}
              transition={enter}
              className="glass absolute left-0 top-[38px] z-50 w-[min(560px,90vw)] p-4 text-left"
              style={{ background: "color-mix(in srgb, #0a0e1a 94%, transparent)" } as CSSProperties}
            >
              <p className="caption mb-2">goal</p>
              <p className="text-[13.5px] leading-relaxed text-(--text)">{state.goal}</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <StatusPill info={info} />
        <RunTimer runId={state.runId} running={running} />
        <RunActions running={running} finished={finished} phase={state.phase} started={Boolean(state.goal)} />
        <ThemeToggle />
      </div>
    </header>
  );
}

function RunActions({
  running,
  finished,
  phase,
  started,
}: {
  running: boolean;
  finished: boolean;
  phase: string;
  started: boolean;
}) {
  const demo = phase === "demo";
  const cancel = (): void => {
    cancelRun().catch((error: unknown) => {
      if (error instanceof RunApiError && error.kind === "network") {
        store.pushToast({ kind: "notice", title: "Agent unreachable", detail: error.message });
      }
    });
  };
  if (running && !demo) {
    return (
      <button type="button" className="btn btn-danger" onClick={cancel} title="Cancel the running agent">
        <Square size={11} />
        Cancel
      </button>
    );
  }
  if ((finished || demo) && started) {
    return <NewRunButton />;
  }
  return null;
}

export function NewRunButton({ label = "New run", withIcon = true }: { label?: string; withIcon?: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className="btn" onClick={() => setOpen(true)} title="Start a new goal">
        {withIcon && <Plus size={12} />}
        {label}
      </button>
      {open && (
        <AnimatePresence>
          <ComposerSheet onClose={() => setOpen(false)} title="New run">
            <MissionComposer className="w-full text-left" />
          </ComposerSheet>
        </AnimatePresence>
      )}
    </>
  );
}

function RunTimer({ runId, running }: { runId: string; running: boolean }) {
  const startedAt = useRef<number | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);

  // A fresh run_id restarts the timer.
  useEffect(() => {
    if (!runId) {
      startedAt.current = null;
      setElapsed(null);
      return;
    }
    startedAt.current = Date.now();
    setElapsed(0);
  }, [runId]);

  // Tick while the run is live; freeze once it is no longer running.
  useEffect(() => {
    if (!runId || !startedAt.current || !running) return;
    const id = window.setInterval(() => {
      if (startedAt.current) setElapsed((Date.now() - startedAt.current) / 1000);
    }, 1000);
    return () => window.clearInterval(id);
  }, [runId, running]);

  if (elapsed === null) return null;
  return (
    <span className="chip num px-2.5" title="Elapsed wall time for this run">
      <span className="caption text-[9px]!">t+</span>
      <span className="font-mono text-[11.5px] font-semibold text-(--text)">{fmtElapsed(elapsed)}</span>
    </span>
  );
}

export const Header = memo(HeaderBase);
