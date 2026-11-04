"use client";

import { memo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Radar, RotateCw } from "lucide-react";
import { selectPhase } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { stringsEqual } from "@/lib/equal";
import { store } from "@/lib/store";
import { SPRING } from "@/lib/motion";

type PhaseState = "connecting" | "live" | "reconnecting" | "demo";

const COPY: Record<Exclude<PhaseState, "live" | "demo">, { label: string; tone: string; retry?: boolean }> = {
  connecting: { label: "Connecting to the agent…", tone: "var(--dim)" },
  reconnecting: { label: "Connection lost — reconnecting", tone: "var(--warn)", retry: true },
};

/** Slim status banner that fades in directly under the header while the SSE
 * stream is not live. */
function SseBannerBase() {
  const phase = useNexus(selectPhase, stringsEqual);
  const copy = COPY[phase as Exclude<PhaseState, "live" | "demo">];

  return (
    <div className="pointer-events-none fixed inset-x-0 top-[76px] z-40 flex justify-center">
      <AnimatePresence>
        {copy && (
          <motion.div
            role="status"
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={SPRING}
            className="pointer-events-auto glass flex items-center gap-2.5 rounded-full border-(--line) px-4 py-1.5"
            style={{ boxShadow: `0 8px 26px -10px rgb(0 0 0 / .5)` }}
          >
            {copy.retry ? (
              <RotateCw size={13} className="shrink-0 animate-spin text-(--warn)" />
            ) : (
              <Radar size={13} className="shrink-0 text-(--dim)" />
            )}
            <span className="text-[12px] font-medium" style={{ color: copy.tone }}>
              {copy.label}
            </span>
            {copy.retry && (
              <button
                type="button"
                className="chip cursor-pointer px-2 py-0 text-[10.5px]! hover:text-(--text)"
                onClick={() => {
                  if (phase === "reconnecting") {
                    // Force an immediate retry instead of waiting out the backoff.
                    store.connect();
                  }
                }}
              >
                Retry now
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export const SseBanner = memo(SseBannerBase);
