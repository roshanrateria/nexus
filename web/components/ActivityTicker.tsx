"use client";

import { memo, useEffect, useRef, useState } from "react";
import { ChevronUp } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { selectLog, selectTicker } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import type { LogEntry, LogKind } from "@/lib/types";
import { SPRING, useEnter } from "@/lib/motion";

const KIND_COLOR: Record<LogKind, string> = {
  plan: "var(--violet)",
  action: "var(--run)",
  ok: "var(--ok)",
  error: "var(--bad)",
  failed: "var(--bad)",
  retry: "var(--warn)",
};

function LogDot({ kind, size = 8 }: { kind: LogKind; size?: number }) {
  const color = KIND_COLOR[kind] ?? "var(--dim)";
  return (
    <span
      aria-hidden="true"
      className="mt-[5px] shrink-0 rounded-full"
      style={{ width: size, height: size, backgroundColor: color, boxShadow: `0 0 8px ${color}` }}
    />
  );
}

function tickTextClass(kind: LogKind): string {
  if (kind === "error" || kind === "failed") return "text-(--bad)";
  if (kind === "plan") return "text-(--violet)";
  if (kind === "retry") return "text-(--warn)";
  return "text-(--dim)";
}

/** The last three log lines (newest types in), plus a "View all" popover
 * with the complete stream. */
function ActivityTickerBase() {
  const tail = useNexus(selectTicker);
  const log = useNexus(selectLog);
  const [open, setOpen] = useState(false);
  const enter = useEnter();

  // Click-away + Escape for the popover.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent): void => {
      const target = e.target as HTMLElement | null;
      if (!target?.closest("[data-log-popover]") && !target?.closest("[data-log-button]")) setOpen(false);
    };
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="relative flex shrink-0 items-center">
      <div className="flex h-[72px] w-full flex-col justify-center gap-1 fill px-3 py-2 pr-[92px]">
        <ol aria-live="polite" className="flex min-w-0 flex-1 flex-col gap-1">
          {tail.length === 0 ? (
            <li className="tick-row text-[11.5px] text-(--faint)">Actions, verdicts and escalations stream here.</li>
          ) : (
            tail.map((entry, i) => {
              const isNewest = i === tail.length - 1;
              return (
                <motion.li
                  key={`${i}-${entry.t}-${entry.text.slice(0, 24)}`}
                  initial={isNewest ? { opacity: 0.25, x: 10, filter: "blur(3px)" } : false}
                  animate={{ opacity: 1, x: 0, filter: "blur(0px)" }}
                  transition={enter}
                  className="tick-row"
                >
                  <LogDot kind={entry.kind} />
                  <time className="shrink-0 pt-[1px] font-mono text-[10px] text-(--faint)">{entry.t}</time>
                  <p className={`min-w-0 flex-1 truncate text-[11.5px] leading-snug ${tickTextClass(entry.kind)}`} title={entry.text}>
                    {entry.text}
                  </p>
                </motion.li>
              );
            })
          )}
        </ol>
      </div>
      <LogBadgeButton count={log.length} open={open} onToggle={() => setOpen((v) => !v)} />
      <AnimatePresence>{open && <FullLogPopover log={log} />}</AnimatePresence>
    </div>
  );
}

function LogBadgeButton({
  count,
  open,
  onToggle,
}: {
  count: number;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      data-log-button=""
      className="chip absolute right-2 bottom-2 z-10 shrink-0 cursor-pointer px-2 py-0 text-[10px]! hover:text-(--text)"
      onClick={onToggle}
      aria-expanded={open}
      title="View the full activity log"
    >
      <ChevronUp size={11} className={open ? "rotate-180 transition-transform" : "transition-transform"} />
      View all
      {count > 0 && <span className="num opacity-70">{count}</span>}
    </button>
  );
}

function FullLogPopover({ log }: { log: LogEntry[] }) {
  const enter = useEnter(SPRING);
  const bodyRef = useRef<HTMLOListElement | null>(null);
  const pinned = useRef(true);

  useEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    const onScroll = (): void => {
      pinned.current = el.scrollTop + el.clientHeight >= el.scrollHeight - 24;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const el = bodyRef.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  });

  return (
    <motion.div
      data-log-popover=""
      role="dialog"
      aria-label="Full activity log"
      initial={{ opacity: 0, y: 8, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.985 }}
      transition={enter}
      className="glass absolute right-0 bottom-[38px] z-50 flex max-h-[min(440px,62vh)] w-[min(600px,72vw)] flex-col p-0"
      style={{ background: "color-mix(in srgb, #0a0e1a 94%, transparent)" }}
    >
      <header className="flex shrink-0 items-center gap-2 border-b border-(--line) px-4 py-2.5">
        <h3 className="caption grow">Full activity log</h3>
        <span className="chip num">{log.length} events</span>
      </header>
      <ol
        ref={bodyRef}
        role="log"
        aria-live="polite"
        className="scroll min-h-0 flex-1 overflow-y-auto px-4 py-2"
      >
        {log.map((entry, i) => (
          <LogRow key={`${i}-${entry.t}-${entry.text.slice(0, 16)}`} entry={entry} />
        ))}
        <li aria-hidden="true" className="h-2" />
      </ol>
    </motion.div>
  );
}

function LogRow({ entry }: { entry: LogEntry }) {
  return (
    <li className="tick-row py-1.5">
      <LogDot kind={entry.kind} />
      <time className="shrink-0 pt-[1px] font-mono text-[10px] text-(--faint)">{entry.t}</time>
      <p className={`min-w-0 flex-1 break-words text-[12px] leading-snug ${tickTextClass(entry.kind)}`}>
        {entry.text}
      </p>
    </li>
  );
}

export const ActivityTicker = memo(ActivityTickerBase);
