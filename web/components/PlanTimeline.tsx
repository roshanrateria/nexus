"use client";

import { motion } from "framer-motion";
import { Check, Clock3 } from "lucide-react";
import { SPRING, useEnter } from "@/lib/motion";
import { memo } from "react";
import { buildTimeline, selectTimeline, type TimelineItem } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { cn } from "@/lib/cn";
import { Panel } from "./ui";

const VERDICT_LABEL: Record<string, string> = {
  retry: "retry",
  replan: "replan",
};

const itemsEqual = (a: TimelineItem[] | undefined, b: TimelineItem[] | undefined): boolean => {
  if (a === b) return true;
  if (!a || !b || a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    const x = a[i];
    const y = b[i];
    if (
      x.key !== y.key ||
      x.state !== y.state ||
      x.instruction !== y.instruction ||
      x.expected !== y.expected ||
      x.assessment !== y.assessment ||
      x.verdict !== y.verdict ||
      x.evidences !== y.evidences
    ) {
      return false;
    }
  }
  return true;
};

const selectTimelineItems = (s: Parameters<typeof selectTimeline>[0]) => {
  const t = selectTimeline(s);
  return buildTimeline(t.history, t.plan);
};

function PlanTimelineBase({ className }: { className?: string }) {
  const timeline = useNexus(selectTimelineItems, itemsEqual);

  return (
    <Panel
      title="Plan timeline"
      right={<span className="chip num">{timeline.length} steps</span>}
      className={cn("lg:col-span-5", className)}
      enterIndex={2}
    >
      <ol className="scroll relative min-h-0 flex-1 overflow-y-auto pr-2">
        {timeline.length === 0 && (
          <EmptyRow />
        )}
        {timeline.map((item, i) => (
          <TimelineRow key={item.key} item={item} index={i} total={timeline.length} />
        ))}
        <li aria-hidden="true" className="h-1" />
      </ol>
    </Panel>
  );
}

export function EmptyRow() {
  return (
    <li className="flex h-full min-h-[120px] flex-col items-center justify-center gap-2 text-center">
      <Clock3 size={20} className="text-(--faint)" />
      <p className="text-[13px] text-(--dim)">No plan yet — the planner drafts steps the moment a goal lands.</p>
    </li>
  );
}

function TimelineRow({ item, index, total }: { item: TimelineItem; index: number; total: number }) {
  const enter = useEnter(SPRING, Math.min(index * 0.03, 0.3));
  return (
    <li className="relative pl-8">
      {/* rail */}
      <span
        aria-hidden="true"
        className="absolute bottom-0 left-[11px] top-2 w-px"
        style={
          index === total - 1
            ? { background: "linear-gradient(to bottom, var(--line), transparent)" }
            : { background: "var(--line)" }
        }
      />
      {/* node */}
      <span className="absolute left-0 top-1 grid h-6 w-6 place-items-center">
        <NodeState state={item.state} />
      </span>
      <motion.div
        initial={{ opacity: 0, x: -14 }}
        animate={{ opacity: 1, x: 0 }}
        transition={enter}
        className={cn(
          "rounded-[14px] border px-3 py-2.5",
          item.state === "active"
            ? "border-(--violet)/35 bg-(--violet)/12 shadow-[0_8px_28px_-8px_rgb(139_92_246/.45)]"
            : item.state === "failed"
              ? "border-(--bad)/25 bg-(--bad)/8"
              : "border-transparent bg-transparent"
        )}
      >
        <div className="flex items-start gap-2">
          <span
            className={cn(
              "caption mt-[3px] shrink-0 rounded-md px-1.5 text-[10px]!",
              item.state === "active" ? "text-(--violet)" : "text-(--faint)"
            )}
          >
            {String(index + 1).padStart(2, "0")}
          </span>
          <div className="min-w-0 flex-1">
            <p
              className={cn(
                "text-[13px] leading-snug",
                item.state === "done" && "text-(--dim)",
                item.state === "active" ? "font-medium text-(--text)" : "text-(--text)"
              )}
            >
              {item.instruction}
            </p>
            <p className="mt-0.5 line-clamp-1 text-[11.5px] text-(--faint)">{item.expected}</p>
            {item.assessment && (
              <p className="mt-1 line-clamp-2 text-[11.5px] leading-snug text-(--dim)">{item.assessment}</p>
            )}
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              {item.verdict && VERDICT_LABEL[item.verdict] && (
                <span
                  className={cn(
                    "chip px-2 py-0 text-[10px]! uppercase!",
                    item.verdict === "retry" ? "text-(--warn)" : "text-(--bad)"
                  )}
                >
                  {VERDICT_LABEL[item.verdict]}
                </span>
              )}
              {item.state === "done" && item.evidences > 0 && (
                <span className="chip px-2 py-0 text-[10px]!">
                  <Check size={10} /> {item.evidences} evidence
                </span>
              )}
              {item.state === "done" && (
                <span className="chip px-2 py-0 text-[10px]! text-(--ok)">verified</span>
              )}
            </div>
          </div>
        </div>
      </motion.div>
    </li>
  );
}

function NodeState({ state }: { state: string }) {
  if (state === "done") {
    return (
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
        <circle cx="10" cy="10" r="8.5" fill="none" stroke="var(--ok)" strokeOpacity=".5" strokeWidth="1.5" />
        <motion.path
          d="M6.2 10.3 L9 13 L14 7.2"
          fill="none"
          stroke="var(--ok)"
          strokeWidth="1.9"
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={SPRING}
        />
      </svg>
    );
  }
  if (state === "failed") {
    return (
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true">
        <circle cx="10" cy="10" r="8.5" fill="none" stroke="var(--bad)" strokeOpacity=".45" strokeWidth="1.5" />
        <motion.path
          d="M7 7 L13 13 M13 7 L7 13"
          fill="none"
          stroke="var(--bad)"
          strokeWidth="1.9"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={SPRING}
        />
      </svg>
    );
  }
  if (state === "active") {
    return (
      <span className="relative grid h-5 w-5 place-items-center">
        <motion.span
          className="absolute h-5 w-5 rounded-full border border-(--violet)/60"
          animate={{ scale: [1, 1.45], opacity: [0.7, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
        />
        <span className="h-3 w-3 rounded-full bg-(--violet) shadow-[0_0_12px_rgb(183_140_247/.8)]" />
      </span>
    );
  }
  return (
    <span className="grid h-5 w-5 place-items-center">
      <span className="h-2.5 w-2.5 rounded-full border border-(--faint)" />
    </span>
  );
}

export const PlanTimeline = memo(PlanTimelineBase);
