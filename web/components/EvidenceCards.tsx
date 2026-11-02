"use client";

import { BadgeCheck, Layers } from "lucide-react";
import { memo } from "react";
import { evidenceListEqual, selectEvidences } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { cn } from "@/lib/cn";
import { Panel } from "./ui";
import { EvidenceThumb, useEvidenceSheet } from "./EvidenceSheet";
import { motion } from "framer-motion";

function EvidenceCardsBase({ className }: { className?: string }) {
  const evidences = useNexus(selectEvidences, evidenceListEqual);

  return (
    <Panel
      title="Evidence"
      right={<span className="chip num">{evidences.length} verified</span>}
      className={cn("lg:col-span-4", className)}
      enterIndex={5}
    >
      {evidences.length === 0 ? (
        <div className="flex h-full min-h-[120px] flex-col items-center justify-center gap-2 text-center">
          <Layers size={20} className="text-(--faint)" />
          <p className="max-w-[300px] text-[13px] leading-snug text-(--dim)">
            Verified verbatim excerpts land here as the verifier grades each step.
          </p>
        </div>
      ) : (
        <div className="scroll -mx-1 flex min-h-0 flex-1 snap-x snap-mandatory gap-2.5 overflow-x-auto px-1 pb-1">
          {evidences.map((evidence, i) => (
            <EvidenceCard key={evidence.id} evidence={evidence} index={i} />
          ))}
        </div>
      )}
    </Panel>
  );
}

function EvidenceCard({ evidence, index }: { evidence: { id: string; url: string; original_text: string; summarized: string; shot?: string }; index: number }) {
  const { open, mutedIds } = useEvidenceSheet();
  const domain = (() => {
    try {
      return new URL(evidence.url).host;
    } catch {
      return evidence.url.slice(0, 30);
    }
  })();

  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 300, damping: 30, delay: Math.min(index * 0.05, 0.4) }}
      whileHover={{ y: -3 }}
      whileTap={{ scale: 0.985 }}
      onClick={() => open(evidence.id)}
      className={cn(
        "fill group relative flex w-[236px] shrink-0 snap-start cursor-pointer flex-col overflow-hidden text-left",
        mutedIds.has(evidence.id) && "opacity-40"
      )}
      aria-label={`Open evidence ${evidence.id}: ${evidence.summarized}`}
    >
      <div className="relative h-[104px] w-full shrink-0 overflow-hidden">
        <EvidenceThumb evidence={evidence} className="absolute inset-0 h-full w-full" />
        <span className="absolute bottom-1.5 left-1.5 z-10 inline-flex items-center gap-1 rounded-full bg-[rgb(4_6_12/.72)] px-2 py-[3px] text-[10px] font-medium uppercase tracking-[.06em] text-(--ok)">
          <BadgeCheck size={10} />
          Verified verbatim
        </span>
        <span className="absolute right-1.5 top-1.5 z-10 font-mono text-[10.5px] font-semibold text-(--text) [text-shadow:0_1px_2px_rgb(0_0_0/.8)]">
          {evidence.id}
        </span>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-1.5 p-3">
        <p className="line-clamp-3 border-l-2 border-(--violet)/60 pl-2 text-[11.5px] italic leading-snug text-(--text)">
          {evidence.original_text}
        </p>
        <p className="line-clamp-2 text-[11.5px] leading-snug text-(--dim)">{evidence.summarized}</p>
        <span className="mt-auto truncate font-mono text-[10.5px] text-(--faint)">{domain}</span>
      </div>
    </motion.button>
  );
}

export const EvidenceCards = memo(EvidenceCardsBase);
