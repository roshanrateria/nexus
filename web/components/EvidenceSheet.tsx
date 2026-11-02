"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { BadgeCheck, Copy, ExternalLink, X } from "lucide-react";
import type { Evidence } from "@/lib/types";
import { shotUrl } from "@/lib/urls";
import { CopyButton, IconButton, StatusDot } from "./ui";
import { SPRING, useEnter } from "@/lib/motion";

interface SheetContextValue {
  open: (id: string) => void;
  close: () => void;
  mutedIds: Set<string>;
  resolve: (id: string) => Evidence | null;
}

const SheetContext = createContext<SheetContextValue | null>(null);

export function useEvidenceSheet(): SheetContextValue {
  const ctx = useContext(SheetContext);
  if (!ctx) throw new Error("useEvidenceSheet must be used inside <EvidenceSheetProvider>");
  return ctx;
}

export function EvidenceSheetProvider({
  evidences,
  children,
}: {
  evidences: Evidence[];
  children: ReactNode;
}) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const byId = useMemo(() => new Map(evidences.map((e) => [e.id, e])), [evidences]);

  const open = useCallback((id: string) => setActiveId(id), []);
  const close = useCallback(() => setActiveId(null), []);
  const resolve = useCallback((id: string) => byId.get(id) ?? null, [byId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  const active = activeId ? byId.get(activeId) ?? null : null;

  const value = useMemo<SheetContextValue>(
    () => ({
      open,
      close,
      mutedIds: new Set(activeId ? [activeId] : []),
      resolve,
    }),
    [open, close, activeId, resolve]
  );

  return (
    <SheetContext.Provider value={value}>
      {children}
      <AnimatePresence>{active && <SheetCard key={active.id} evidence={active} />}</AnimatePresence>
    </SheetContext.Provider>
  );
}

function SheetCard({ evidence }: { evidence: Evidence }) {
  const { close } = useEvidenceSheet();
  const enter = useEnter(SPRING);
  const url = shotUrl(evidence.shot);

  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "";
    };
  }, []);

  return (
    <>
      <motion.div
        className="fixed inset-0 z-50 bg-[rgb(4_6_12/.62)]"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.25 }}
        onClick={close}
        aria-hidden="true"
      />
      <motion.aside
        role="dialog"
        aria-modal="true"
        aria-label={`Evidence ${evidence.id}`}
        initial={{ x: 80, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 80, opacity: 0 }}
        transition={enter}
        className="glass fixed bottom-3 right-3 top-3 z-50 flex w-[min(560px,calc(100vw-24px))] flex-col overflow-hidden p-0"
      >
        <header className="flex shrink-0 items-center gap-2 px-5 py-4">
          <span className="chip font-medium text-(--text)">{evidence.id}</span>
          <span className="chip flex-1 overflow-hidden">
            <ExternalLink size={11} className="shrink-0" />
            <span className="truncate">{evidence.url}</span>
          </span>
          <IconButton label="Close evidence sheet" onClick={close}>
            <X size={15} />
          </IconButton>
        </header>
        <div className="scroll min-h-0 flex-1 overflow-y-auto px-5 pb-6">
          {url && (
            <div className="overflow-hidden rounded-[20px] border border-(--line) bg-[#0a0f1a]">
              <motion.div layoutId={`ev-${evidence.id}`}>
                <img src={url} alt={`Screenshot for ${evidence.id}`} className="block w-full" />
              </motion.div>
            </div>
          )}
          <div className="mt-4 flex items-center justify-between">
            <span className="chip text-(--ok)" style={{ color: "var(--ok)" }}>
              <BadgeCheck size={12} />
              Verified verbatim
            </span>
            <CopyButton text={evidence.original_text} label="Copy excerpt" />
          </div>
          <p className="mt-3 border-l-2 border-(--violet) pl-3 text-[13.5px] italic leading-relaxed text-(--text)">
            “{evidence.original_text}”
          </p>
          <p className="mt-3 text-[13px] leading-relaxed text-(--dim)">{evidence.summarized}</p>
          <a
            href={evidence.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-4 block break-all text-[11.5px] text-(--run) hover:underline"
          >
            {evidence.url}
          </a>
        </div>
      </motion.aside>
    </>
  );
}

/** Shared morphable thumbnail; suppresses its layoutId while the sheet for
 * this evidence is open. */
export function EvidenceThumb({
  evidence,
  className,
  children,
}: {
  evidence: Evidence;
  className?: string;
  children?: ReactNode;
}) {
  const url = shotUrl(evidence.shot);
  return (
    <motion.div
      layoutId={`ev-${evidence.id}`}
      className={className}
    >
      {url ? (
        <img src={url} alt={`Frame for ${evidence.id}`} className="h-full w-full object-cover" loading="lazy" />
      ) : (
        <div className="h-full w-full bg-gradient-to-br from-(--violet)/50 to-(--cyan)/40" />
      )}
      {children}
    </motion.div>
  );
}

export function EvidenceChip({ id }: { id: string }) {
  const { resolve, open } = useEvidenceSheet();
  const evidence = resolve(id);
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        open(id);
      }}
      className="inline-flex items-center gap-1 rounded-[8px] border border-(--line) bg-(--fill-strong) px-1.5 py-[1px] align-baseline font-mono text-[11px] text-(--violet) transition-colors hover:border-(--violet)/50 hover:text-(--violet) cursor-pointer"
      aria-label={evidence ? `Open evidence ${id}` : `Evidence ${id} not available`}
      title={evidence ? evidence.summarized : `${id} not in this run's evidence`}
    >
      {evidence ? <BadgeCheck size={10} className="shrink-0 opacity-80" /> : <StatusDot color="var(--faint)" />}
      {id}
    </button>
  );
}

export function SheetCopyHint() {
  return (
    <span className="caption inline-flex items-center gap-1">
      <Copy size={11} /> copyable
    </span>
  );
}
