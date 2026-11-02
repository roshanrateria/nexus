"use client";

import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Sparkles, TriangleAlert } from "lucide-react";
import { SPRING } from "@/lib/motion";
import { stringsEqual } from "@/lib/equal";
import { selectToastState } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { store } from "@/lib/store";
import { cn } from "@/lib/cn";

export function Toasts() {
  const { toasts } = useNexus(selectToastState, shallowToastEqual);
  // The docked mission composer owns the bottom strip while a run exists;
  // notices then float above it instead of underneath.
  const goal = useNexus((s) => s.data?.goal ?? "", stringsEqual);

  return (
    <div
      className={cn(
        "pointer-events-none fixed inset-x-0 z-[70] flex flex-col items-center gap-2 px-4",
        goal ? "bottom-24" : "bottom-4"
      )}
      aria-live="polite"
    >
      <AnimatePresence>
        {toasts.map((toast) => (
          <ToastItem key={toast.id} id={toast.id} kind={toast.kind} title={toast.title} detail={toast.detail} />
        ))}
      </AnimatePresence>
    </div>
  );
}

function ToastItem({ id, kind, title, detail }: { id: string; kind: "escalation" | "notice"; title: string; detail: string }) {
  useEffect(() => {
    const t = window.setTimeout(() => store.dismissToast(id), 5200);
    return () => window.clearTimeout(t);
  }, [id]);

  return (
    <motion.div
      role="status"
      initial={{ opacity: 0, y: 24, scale: 0.94 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 12, scale: 0.96 }}
      transition={SPRING}
      className="pointer-events-auto toast flex items-center gap-3 px-4 py-3 shadow-[0_16px_40px_-12px_rgb(0_0_0/.5)]"
    >
      {kind === "escalation" ? (
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-(--violet)/15 text-(--violet)">
          <Sparkles size={17} />
        </span>
      ) : (
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-(--warn)/15 text-(--warn)">
          <TriangleAlert size={17} />
        </span>
      )}
      <span className="flex flex-col">
        <span className="text-[13.5px] font-semibold text-(--text)">{title}</span>
        <span className="text-[12px] text-(--dim)">{detail}</span>
      </span>
      <button
        type="button"
        onClick={() => store.dismissToast(id)}
        className="ml-3 shrink-0 rounded-lg px-2 py-1 text-[11.5px] font-medium text-(--dim) transition-colors hover:bg-(--fill) hover:text-(--text)"
      >
        dismiss
      </button>
    </motion.div>
  );
}

function shallowToastEqual(
  a: { toasts: { id: string; kind?: string; title: string; detail: string }[] } | undefined,
  b: { toasts: { id: string; kind?: string; title: string; detail: string }[] } | undefined
): boolean {
  if (a === b) return true;
  if (!a || !b || a.toasts.length !== b.toasts.length) return false;
  for (let i = 0; i < a.toasts.length; i++) {
    if (a.toasts[i].id !== b.toasts[i].id) return false;
  }
  return true;
}
