"use client";

import { memo, type CSSProperties } from "react";
import { headerEqual, selectHeader } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { statusInfo } from "@/lib/statusMap";
import { CopyButton, LogoGlyph, StatusDot, StatusPill } from "./ui";
import { ThemeToggle } from "./ThemeToggle";

const PHASE_LABEL: Record<string, { label: string; color: string; pulse: boolean }> = {
  connecting: { label: "Connecting", color: "var(--dim)", pulse: true },
  reconnecting: { label: "Reconnecting", color: "var(--warn)", pulse: true },
  live: { label: "Live", color: "var(--ok)", pulse: false },
  demo: { label: "Demo", color: "var(--violet)", pulse: true },
};

function HeaderBase() {
  const state = useNexus(selectHeader, headerEqual);
  const info = statusInfo(state.status, state.outcome);
  const phase = PHASE_LABEL[state.phase] ?? { label: state.phase, color: "var(--dim)", pulse: true };

  return (
    <header className="glass relative col-span-1 flex min-h-[64px] items-center gap-3 px-4 py-2.5 md:col-span-2 md:px-5 md:py-3 lg:col-span-12">
      <div className="flex shrink-0 items-center gap-2.5">
        <LogoGlyph size={34} />
        <div className="hidden flex-col leading-none sm:flex">
          <span className="text-[15px] font-semibold tracking-[0.02em]">NEXUS</span>
          <span className="caption mt-0.5">agentic browser</span>
        </div>
      </div>

      <div className="hidden h-9 w-px bg-(--line) xl:block" />

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex min-w-0 items-center gap-2">
          <span className="caption shrink-0">goal</span>
          <p className="truncate text-[13.5px] font-medium text-(--text)" title={state.goal}>
            {state.goal || <span className="text-(--faint)">waiting for a goal…</span>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill info={info} />
          <span className="chip" style={{ color: phase.color } as CSSProperties}>
            <StatusDot pulse={phase.pulse} color={phase.color} />
            {phase.label}
          </span>
          {state.runId && (
            <span className="chip flex items-center gap-1.5">
              <span className="font-mono">run</span>
              <span className="font-mono text-(--text)">{state.runId}</span>
              <CopyButton compact text={state.runId} label="Copy run id" />
            </span>
          )}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <ThemeToggle />
      </div>
    </header>
  );
}

export const Header = memo(HeaderBase);
