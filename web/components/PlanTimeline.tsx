"use client";

import { memo, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Check, ChevronDown, Clock3, RefreshCcw, Route, Trash2 } from "lucide-react";
import { SPRING, useEnter } from "@/lib/motion";
import { buildTimeline, selectTimeline, type TimelineItem } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { cn } from "@/lib/cn";
import { CountBadge, Panel, PanelEmpty } from "./ui";

const VERDICT_META: Record<string, { label: string; tone: string; icon: React.ReactNode }> = {
  retry: { label: "retry", tone: "var(--warn)", icon: <RefreshCcw size={9} /> },
  replan: { label: "replan", tone: "var(--bad)", icon: <Trash2 size={9} /> },
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

/** Left column: compact step cards for the plan + executed history.-active
 * card glows; finished cards show a verdict chip; cards expand on click to
 * reveal the expected outcome / assessment. */
function PlanTimelineBase({ className }: { className?: string }) {
  const timeline = useNexus(selectTimelineItems, itemsEqual);
  const enter = useEnter(SPRING);

  // Keep the active card visible without yanking the scroll position during
  // streaming.
  const listRef = useRef<HTMLOListElement | null>(null);
  const activeIndex = timeline.findIndex((t) => t.state === "active");
  useEffect(() => {
    const list = listRef.current;
    if (activeIndex < 0 || !list) return;
    const child = list.children[activeIndex] as HTMLElement | undefined;
    if (!child) return;
    child.scrollIntoView({ block: "nearest" });
  }, [activeIndex, timeline.length]);

  return (
    <Panel
      title="Plan"
      count={timeline.length > 0 ? timeline.length : undefined}
      action={
        activeIndex >= 0 ? (
          <span className="chip text-(--violet)">
            <Clock3 size={10} />
            step {activeIndex + 1} running
          </span>
        ) : undefined
      }
      className={className}
      bodyClassName="flex flex-col"
    >
      {timeline.length === 0 ? (
        <PanelEmpty
          icon={<Route size={20} />}
          title="No plan yet."
          hint="The planner writes numbered steps here; the executor works through them one by one."
        />
      ) : (
        <ol ref={listRef} className="flex flex-col gap-1.5">
          {timeline.map((item, i) => (
            <TimelineRow key={item.key} item={item} index={i} enter={enter} />
          ))}
        </ol>
      )}
    </Panel>
  );
}

function TimelineRow({
  item,
  index,
  enter,
}: {
  item: TimelineItem;
  index: number;
  enter: ReturnType<typeof useEnter>;
}) {
  const [open, setOpen] = useState(false);
  const done = item.state === "done";
  const active = item.state === "active";
  const failed = item.state === "failed";
  const verdict = VERDICT_META[item.verdict ?? ""];

  return (
    <motion.li
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={enter}
      data-testid="plan-step"
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "row-card w-full cursor-pointer p-2.5 text-left",
          active && "!border-(--violet)/45 bg-(--violet)/8",
          "focus-visible:outline-2 focus-visible:outline-(--focus)"
        )}
        style={active ? { boxShadow: "0 0 0 1px color-mix(in srgb, var(--violet) 25%, transparent), 0 6px 22px -8px color-mix(in srgb, var(--violet) 45%, transparent)" } : undefined}
      >
        <span className="flex items-start gap-2.5">
          <span
            aria-hidden="true"
            className={cn(
              "num grid h-5 w-5 shrink-0 translate-y-0.5 place-items-center rounded-full border text-[10px] font-bold",
              done && "border-(--ok)/40 bg-(--ok)/15 text-(--ok)",
              active && "border-(--violet)/55 bg-(--violet)/18 text-(--violet)",
              failed && "border-(--bad)/45 bg-(--bad)/12 text-(--bad)",
              item.state === "queued" && "border-(--line) text-(--faint)"
            )}
          >
            {done ? <Check size={11} /> : failed ? verdict?.icon : index + 1}
          </span>
          <span className="flex min-w-0 flex-1 flex-col gap-1">
            <span
              className={cn(
                "text-[12px] font-medium leading-snug",
                item.state === "queued" ? "text-(--dim)" : "text-(--text)"
              )}
              style={{ display: "-webkit-box", WebkitLineClamp: open ? undefined : 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}
            >
              {item.instruction}
            </span>
            {open && (
              <span className="flex flex-col gap-1 border-t border-(--line) pt-1.5">
                <span className="text-[11px] leading-snug text-(--dim)">
                  <span className="font-semibold text-(--faint)">expected</span> {item.expected}
                </span>
                {item.assessment && (
                  <span className="text-[11px] leading-snug text-(--warn)">
                    <span className="font-semibold opacity-80">verifier</span> {item.assessment}
                  </span>
                )}
                {item.evidences > 0 && <CountBadge value={`${item.evidences} evidence`} />}
              </span>
            )}
          </span>
          <span className="flex shrink-0 items-center gap-1.5">
            {failed && verdict && (
              <span
                className="chip px-1.5 py-0 text-[9.5px]!"
                style={{ color: verdict.tone, borderColor: `color-mix(in srgb, ${verdict.tone} 40%, transparent)`, background: `color-mix(in srgb, ${verdict.tone} 10%, transparent)` }}
              >
                {verdict.icon}
                {verdict.label}
              </span>
            )}
            {item.evidences > 0 && done && (
              <span className="chip px-1.5 py-0 text-[9.5px]!">{item.evidences}</span>
            )}
            <ChevronDown size={12} className={cn("shrink-0 text-(--faint) transition-transform", open && "rotate-180")} />
          </span>
        </span>
      </button>
    </motion.li>
  );
}

export const PlanTimeline = memo(PlanTimelineBase);
