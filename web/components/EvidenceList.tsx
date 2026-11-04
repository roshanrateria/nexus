"use client";

import { memo, useState } from "react";
import { motion } from "framer-motion";
import { BadgeCheck, FileSearch, ExternalLink } from "lucide-react";
import { selectEvidences, evidenceListEqual } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { hostOf, shotUrl } from "@/lib/urls";
import { useEvidenceSheet, EvidenceThumb } from "./EvidenceSheet";
import { SPRING, useEnter } from "@/lib/motion";
import { Panel, PanelEmpty } from "./ui";
import { cn } from "@/lib/cn";

/** Right column: vertical evidence cards. Click opens the full sheet with
 * the verbatim excerpt and screenshot. */
function EvidenceListBase({ className }: { className?: string }) {
  const evidences = useNexus(selectEvidences, evidenceListEqual);
  const { open } = useEvidenceSheet();
  const enter = useEnter(SPRING);

  return (
    <Panel
      title="Evidence"
      count={evidences.length}
      className={className}
      bodyClassName="flex flex-col"
      scroll
    >
      {evidences.length === 0 ? (
        <PanelEmpty
          icon={<FileSearch size={20} />}
          title="No evidence captured yet."
          hint="Verbatim quotes (with the frame screenshot) land here the moment the verifier accepts them."
        />
      ) : (
        <ol className="flex flex-col gap-2">
          {[...evidences].reverse().map((evidence) => (
            <motion.li key={evidence.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={enter}>
              <EvidenceCard evidence={evidence} onOpen={() => open(evidence.id)} />
            </motion.li>
          ))}
          <li aria-hidden="true" className="h-1" />
        </ol>
      )}
    </Panel>
  );
}

function EvidenceCard({
  evidence,
  onOpen,
}: {
  evidence: Parameters<typeof EvidenceThumb>[0]["evidence"];
  onOpen: () => void;
}) {
  const [hover, setHover] = useState(false);
  const host = hostOf(evidence.url);
  const src = shotUrl(evidence.shot);

  return (
    <button
      type="button"
      onClick={onOpen}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className={cn(
        "row-card block w-full cursor-pointer overflow-hidden p-0 text-left",
        "focus-visible:outline-2 focus-visible:outline-(--focus)"
      )}
      aria-label={`Open evidence ${evidence.id}: ${evidence.summarized}`}
      title="Open the evidence sheet"
    >
      <div className="flex min-w-0 items-center gap-2 px-3 pt-2.5 pb-1.5">
        <span className="chip shrink-0 border-(--violet)/30 bg-(--violet)/12 font-mono! text-[10.5px]! text-(--violet)">
          {evidence.id}
        </span>
        <span className="chip min-w-0 flex-1 justify-start" title={evidence.url}>
          <ExternalLink size={10} className="shrink-0 opacity-70" />
          <span className="truncate text-[10.5px]">{host || evidence.url}</span>
        </span>
        <span className="chip shrink-0 text-(--ok)">
          <BadgeCheck size={10} className="shrink-0" />
          Verified
        </span>
      </div>
      <div className="relative h-[92px] w-full overflow-hidden">
        <EvidenceThumb evidence={evidence} className="absolute inset-0">
          {src && (
            <span
              aria-hidden="true"
              className={cn(
                "absolute inset-0 transition-colors",
                hover ? "bg-(--violet)/14" : "bg-transparent"
              )}
            />
          )}
        </EvidenceThumb>
        {!src && (
          <span aria-hidden="true" className="absolute inset-0 bg-gradient-to-br from-(--violet)/35 to-(--cyan)/25" />
        )}
      </div>
      <div className="px-3 pt-1.5 pb-2.5">
        <p className="line-clamp-3 border-l-2 border-(--violet) pl-2 text-[11.5px] italic leading-snug text-(--text)">
          “{evidence.original_text}”
        </p>
        <p className={cn("line-clamp-2 mt-1 text-[11.5px] leading-snug", hover ? "text-(--dim)" : "text-(--faint)")}>
          {evidence.summarized}
        </p>
      </div>
    </button>
  );
}

export const EvidenceList = memo(EvidenceListBase);
