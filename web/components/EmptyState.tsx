"use client";

import { motion } from "framer-motion";
import { LogoGlyph } from "./ui";
import { useEnter } from "@/lib/motion";
import { selectPhase } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { cn } from "@/lib/cn";

const PHASE_TEXT: Record<string, string> = {
  connecting: "connecting…",
  reconnecting: "reconnecting…",
  demo: "demo replay",
  live: "live feed",
};

export function EmptyState({ inFrame, className }: { inFrame?: boolean; className?: string }) {
  const phase = useNexus(selectPhase);
  const enter = useEnter({ duration: 0.4 });
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={enter}
      className={cn(
        "flex flex-col items-center gap-2 text-center",
        inFrame ? "px-4" : "py-2",
        className
      )}
    >
      <motion.div
        animate={{ y: [0, -5, 0] }}
        transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
      >
        <LogoGlyph size={inFrame ? 40 : 46} />
      </motion.div>
      <p className="text-[14px] font-medium text-(--text)">Waiting for the agent</p>
      <p className="text-[12.5px] leading-snug text-(--dim)">
        Connection status: <span className="font-medium text-(--text)">{PHASE_TEXT[phase] ?? phase}</span>
      </p>
      <p className="max-w-[300px] text-[11.5px] leading-snug text-(--faint)">
        Start a run with <code className="font-mono">python runner.py &quot;…&quot;</code> — or watch the scripted
        showcase at <code className="font-mono text-(--violet)">/?demo=1</code>.
      </p>
    </motion.div>
  );
}
