"use client";

import { memo, useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { selectGoalString, selectRunId, selectStatusString } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { stringsEqual } from "@/lib/equal";
import { useFrames } from "@/lib/frames";
import { useStage, type StageTab } from "@/lib/stage";
import { Segmented, LogoGlyph } from "./ui";
import { BrowserWindow } from "./BrowserWindow";
import { ReportPanel } from "./ReportPanel";
import { GraphStage } from "./GraphStage";
import { ActivityTicker } from "./ActivityTicker";
import { MissionComposer } from "./MissionComposer";

interface SegmentOptions {
  id: StageTab;
  label: string;
  hotkey: string;
  testId: string;
}

const TAB_OPTIONS: SegmentOptions[] = [
  { id: "live", label: "Live", hotkey: "1", testId: "tab-live" },
  { id: "report", label: "Report", hotkey: "2", testId: "tab-report" },
  { id: "graph", label: "Graph", hotkey: "3", testId: "tab-graph" },
];

function CenterColumnBase({ className }: { className?: string }) {
  const { tab, setTab, goLive } = useStage();
  const { returnToLive } = useFrames();
  const goal = useNexus(selectGoalString, stringsEqual);
  const runId = useNexus(selectRunId, stringsEqual);
  const status = useNexus(selectStatusString, stringsEqual);
  const hasRun = Boolean(goal);

  // Auto-select Report when the agent starts writing it.
  const prevStatus = useRef("");
  useEffect(() => {
    if (status === "reporting" && prevStatus.current !== "reporting") setTab("report");
    prevStatus.current = status;
  }, [status, setTab]);

  // A fresh run_id resets the stage to Live.
  const prevRun = useRef("");
  useEffect(() => {
    if (runId && prevRun.current !== runId) {
      setTab("live");
      returnToLive();
    }
    prevRun.current = runId;
  }, [runId, setTab, returnToLive]);

  // 1/2/3 tabs, L live; never while typing or when any sheet/popover holds focus.
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName ?? "";
      if (
        target?.isContentEditable ||
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        tag === "SELECT" ||
        document.querySelector("[role='dialog']")
      ) {
        return;
      }
      const map: Record<string, StageTab> = { "1": "live", "2": "report", "3": "graph" };
      if (e.key in map) {
        e.preventDefault();
        setTab(map[e.key]);
      } else if (e.key === "l" || e.key === "L") {
        e.preventDefault();
        returnToLive();
        goLive();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setTab, goLive, returnToLive]);

  return (
    <section className={className ?? ""}>
      <header className="flex shrink-0 items-center gap-3 pb-3">
        <Segmented options={TAB_OPTIONS.map((t) => ({ id: t.id, label: t.label, hotkey: t.hotkey }))} value={tab} onChange={(id) => setTab(id as StageTab)} />
      </header>

      <div className="flex min-h-0 flex-1 flex-col">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={hasRun ? tab : "idle"}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.12 }}
            className="flex min-h-0 flex-1 flex-col"
          >
            {hasRun ? (
              tab === "live" ? <BrowserWindow /> : tab === "report" ? <ReportPanel /> : <GraphStage />
            ) : (
              <IdleHero />
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {hasRun && <ActivityTicker />}
    </section>
  );
}

function IdleHero() {
  return (
    <div className="fill scroll flex h-full min-h-0 w-full flex-col items-center justify-center overflow-y-auto rounded-[16px] px-6 py-8">
      <div className="mx-auto flex w-full max-w-[660px] flex-col items-center text-center">
        <LogoGlyph size={54} />
        <h1 className="mt-4 text-[21px] font-semibold tracking-[-0.01em] text-(--text)">
          Mission control for your browser agent
        </h1>
        <p className="mt-1.5 max-w-[460px] text-[13px] leading-relaxed text-(--dim)">
          Cloud brain, open-weights hands. Every run streams its screenshots, plan, evidence and final report here.
        </p>
        <MissionComposer className="mt-6 w-full text-left" />
        <p className="mt-4 max-w-[420px] text-[11.5px] leading-snug text-(--faint)">
          Or start one from the CLI with <code className="font-mono">python runner.py &quot;…&quot;</code> — and watch
          the scripted showcase at <code className="font-mono text-(--violet)">/?demo=1</code>.
        </p>
      </div>
    </div>
  );
}

export const CenterColumn = memo(CenterColumnBase);
