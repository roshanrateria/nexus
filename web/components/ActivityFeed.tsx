"use client";

import { useEffect, useRef, memo } from "react";
import { motion } from "framer-motion";
import { logEqual, selectLog } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { useEnter } from "@/lib/motion";
import { cn } from "@/lib/cn";
import { Panel } from "./ui";
import type { LogKind } from "@/lib/types";

const KIND_COLOR: Record<LogKind, string> = {
  plan: "var(--violet)",
  action: "var(--run)",
  ok: "var(--ok)",
  error: "var(--bad)",
  failed: "var(--bad)",
  retry: "var(--warn)",
};

function ActivityFeedBase({ className }: { className?: string }) {
  const log = useNexus(selectLog, logEqual);
  const bodyRef = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);

  useEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    const onScroll = (): void => {
      pinned.current = el.scrollTop + el.clientHeight >= el.scrollHeight - 28;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const el = bodyRef.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [log]);

  return (
    <Panel
      title="Live activity"
      right={<span className="chip num">{log.length} events</span>}
      className={cn("lg:col-span-3 lg:row-span-2", className)}
      enterIndex={4}
      bodyClassName="flex flex-col"
    >
      <div
        ref={bodyRef}
        className="scroll min-h-0 flex-1 overflow-y-auto pr-1"
        role="log"
        aria-live="polite"
        aria-label="Agent activity feed"
      >
        {log.length === 0 ? (
          <FeedPlaceholder />
        ) : (
          (() => {
            const visible = log.slice(-60);
            const offset = log.length - visible.length;
            return visible.map((entry, i) => (
              <FeedRow
                key={`${offset + i}-${entry.t}-${entry.kind}`}
                entry={entry}
                latest={i === visible.length - 1}
              />
            ));
          })()
        )}
        <div aria-hidden="true" className="h-2" />
      </div>
    </Panel>
  );
}

function FeedPlaceholder() {
  return (
    <div className="flex h-full items-center justify-center p-4">
      <p className="text-center text-[13px] text-(--dim)">
        Actions, verdicts and escalations stream here in real time.
      </p>
    </div>
  );
}

function FeedRow({
  entry,
  latest,
}: {
  entry: { t: string; kind: LogKind; text: string };
  latest: boolean;
}) {
  const enter = useEnter();
  const color = KIND_COLOR[entry.kind] ?? "var(--dim)";
  const body = (
    <>
      <span
        className="mt-[5px] h-2 w-2 shrink-0 rounded-full"
        style={{ backgroundColor: color, boxShadow: `0 0 8px ${color}` }}
      />
      <time className="shrink-0 pt-[1px] font-mono text-[10.5px] text-(--faint)">{entry.t}</time>
      <p
        className={cn(
          "min-w-0 flex-1 break-words text-[12.5px] leading-snug",
          entry.kind === "error" || entry.kind === "failed"
            ? "text-(--bad)"
            : entry.kind === "plan"
              ? "text-(--violet)"
              : entry.kind === "retry"
                ? "text-(--warn)"
                : "text-(--dim)"
        )}
      >
        {entry.text}
      </p>
    </>
  );

  return (
    <motion.div
      initial={latest ? { opacity: 0.25, y: 10, filter: "blur(3px)" } : false}
      animate={latest ? { opacity: 1, y: 0, filter: "blur(0px)" } : undefined}
      transition={enter}
      className="flex gap-2 py-1"
    >
      {body}
    </motion.div>
  );
}

export const ActivityFeed = memo(ActivityFeedBase);
