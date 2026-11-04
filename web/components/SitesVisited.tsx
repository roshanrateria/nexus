"use client";

import { memo, useMemo } from "react";
import { Globe, Repeat2, BadgeCheck } from "lucide-react";
import { visitedEqual, selectVisited, selectEvidences } from "@/lib/selectors";
import { evidenceCountEqual } from "@/lib/graphData";
import { useNexus } from "@/lib/useNexus";
import { hostGradient, pathSnippet, splitUrl } from "@/lib/urls";
import { useFrames } from "@/lib/frames";
import { useStage } from "@/lib/stage";
import { fmtInt } from "@/lib/format";
import { SPRING } from "@/lib/motion";
import { motion } from "framer-motion";
import { Panel, PanelEmpty } from "./ui";
import { cn } from "@/lib/cn";

/** Sites the agent has loaded this run, newest visit first, deduped by the
 * backend (`visited`). Clicking a row pins its most recent frame in the
 * filmstrip and jumps the stage to Live. */
function SitesVisitedBase({ className }: { className?: string }) {
  const sites = useNexus(selectVisited, visitedEqual);
  const evidences = useNexus(selectEvidences, evidenceCountEqual);
  const { pinUrl } = useFrames();
  const { goLive } = useStage();

  // Evidence count per host, so rows can show how well sourced a site is.
  const evidenceByHost = useMemo(() => {
    const map = new Map<string, number>();
    for (const ev of evidences) {
      const host = splitUrl(ev.url).host;
      if (host) map.set(host, (map.get(host) ?? 0) + 1);
    }
    return map;
  }, [evidences]);

  const open = (url: string): void => {
    pinUrl(url);
    goLive();
  };

  return (
    <Panel
      title="Sites visited"
      count={sites.length}
      className={className}
      bodyClassName="flex flex-col"
      scroll
      testId="sites-list"
    >
      {sites.length === 0 ? (
        <PanelEmpty
          icon={<Globe size={20} />}
          title="No pages visited yet."
          hint="Each unique URL the agent opens is tracked here — deduped, with a revisit counter."
        />
      ) : (
        <ol className="flex flex-col gap-1">
          {sites.map((site, i) => {
            const g = hostGradient(site.host);
            const evCount = evidenceByHost.get(site.host) ?? 0;
            const snippet = pathSnippet(site.url);
            return (
              <motion.li
                key={site.url}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ ...(i === 0 ? SPRING : { duration: 0.25 }), delay: i === 0 ? 0 : i > 5 ? 0 : i * 0.03 }}
              >
                <button
                  type="button"
                  onClick={() => open(site.url)}
                  className={cn(
                    "row-card flex w-full items-center gap-2.5 px-2 py-1.5",
                    "cursor-pointer focus-visible:outline-2 focus-visible:outline-(--focus)"
                  )}
                  title={`Pin the latest frame of ${site.url}`}
                >
                  {/* deterministic monogram avatar */}
                  <span
                    aria-hidden="true"
                    className="grid h-7 w-7 shrink-0 place-items-center rounded-[10px] text-[11px] font-bold text-[#0b1020]"
                    style={{ background: `linear-gradient(135deg, ${g.from}, ${g.to})` }}
                  >
                    {(site.host.replace(/^www\./, "")[0] ?? "?").toUpperCase()}
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="truncate text-[12px] font-medium text-(--text)" title={site.title || site.url}>
                      {site.title || site.host}
                    </span>
                    <span className="truncate font-mono text-[10px] text-(--faint)">
                      {snippet ? `${site.host.replace(/^www\./, "")}${snippet.startsWith("/") ? "" : " · "}${snippet}` : site.host.replace(/^www\./, "")}
                    </span>
                  </span>
                  <span className="flex shrink-0 flex-col items-end gap-0.5">
                    {site.visits > 1 && (
                      <span className="chip px-1.5 py-0 text-[9.5px]!">
                        <Repeat2 size={9} className="shrink-0" />
                        {site.visits}
                      </span>
                    )}
                    {evCount > 0 && (
                      <span className="chip px-1.5 py-0 text-[9.5px]! text-(--ok)">
                        <BadgeCheck size={9} className="shrink-0" />
                        {fmtInt(evCount)}
                      </span>
                    )}
                  </span>
                </button>
              </motion.li>
            );
          })}
          <li aria-hidden="true" className="h-1" />
        </ol>
      )}
    </Panel>
  );
}

export const SitesVisited = memo(SitesVisitedBase);
