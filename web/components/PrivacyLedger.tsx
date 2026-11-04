"use client";

import { memo } from "react";
import { ShieldCheck, ShieldAlert, Sparkles } from "lucide-react";
import { fmtBytes, fmtCompact, fmtPct } from "@/lib/format";
import { privacyEqual, selectPrivacy } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { Ticker, Panel } from "./ui";
import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

/** Compact privacy ledger (right column, top): which brain got billed, how
 * many screenshots ever left the machine, and where tokens ran. */
function PrivacyLedgerBase({ className }: { className?: string }) {
  const d = useNexus(selectPrivacy, privacyEqual);
  const cloudOnly = d.mode === "cloud";
  const imagesOut = d.imagesOut;

  return (
    <Panel
      title="Privacy ledger"
      action={<ModeBadge mode={d.mode} />}
      className={className}
      bodyClassName="flex flex-col gap-2.5"
      scroll={false}
      testId="ledger"
    >
      {/* headline number: screenshots to cloud */}
      <HeadlineRow
        icon={imagesOut > 0 ? <ShieldAlert size={14} className="text-(--warn)" /> : <ShieldCheck size={14} className="text-(--ok)" />}
        value={
          <Ticker
            value={imagesOut}
            className={cn("text-3xl font-bold leading-none tracking-tight", imagesOut > 0 ? "text-(--warn)" : "text-(--ok)")}
          />
        }
        label={imagesOut === 1 ? "screenshot sent to cloud" : "screenshots sent to cloud"}
        copy={
          imagesOut > 0
            ? "Frames the executor saw were uploaded with cloud prompts — the browser stays yours, the copying is honest."
            : "Every frame the executor sees is billed to open weights. Enforced by the ledger, not by convention."
        }
      />

      {/* headline number two: open-weights token share */}
      <HeadlineRow
        icon={<Sparkles size={14} className="text-(--violet)" />}
        value={
          <span className={cn("text-3xl font-bold leading-none tracking-tight text-(--violet)")}>{fmtPct(d.share)}</span>
        }
        label="of billed tokens ran open-weights"
        copy={cloudOnly ? "The planner, executor, verifier and reporter all billed the Meta Model API." : "Planner + reporter on the frontier model; executor + verifier kept local."}
      />

      {/* tiny cloud-vs-open table */}
      <div className="fill overflow-hidden">
        <table className="w-full text-[10.5px] leading-tight">
          <thead>
            <tr className="caption text-[9px]!">
              <th className="px-2.5 py-1.5 text-left font-semibold">meter</th>
              <th className="px-2.5 py-1.5 text-right font-semibold">cloud</th>
              <th className="px-2.5 py-1.5 text-right font-semibold">open</th>
            </tr>
          </thead>
          <tbody className="num text-(--dim)">
            <LedgerRow label="calls" cloud={fmtCompact(d.cloudCalls)} open={fmtCompact(d.openCalls)} />
            <LedgerRow label="tokens" cloud={fmtCompact(d.cloudTokens)} open={fmtCompact(d.openTokens)} />
            <LedgerRow label="bytes out" cloud={fmtBytes(d.cloudBytes)} open={fmtBytes(d.openBytes)} />
          </tbody>
        </table>
      </div>

      <p className="caption truncate text-[10px]!" title={`Planner consulted ${d.plannerCalls} × over ${d.steps} steps`}>
        Frontier model consulted {d.plannerCalls} × for {d.steps} steps
      </p>
    </Panel>
  );
}

function HeadlineRow({ icon, value, label, copy }: { icon: ReactNode; value: ReactNode; label: string; copy: string }) {
  return (
    <div className="flex items-start gap-3">
      <span className="fill grid h-11 w-11 shrink-0 place-items-center">{icon}</span>
      <span className="flex min-w-0 flex-col">
        <span className="flex flex-wrap items-baseline gap-x-2">{value}<span className="text-[12px] font-semibold text-(--text)">{label}</span></span>
        <span className="mt-0.5 text-[10.5px] leading-snug text-(--faint)">{copy}</span>
      </span>
    </div>
  );
}

function LedgerRow({ label, cloud, open }: { label: string; cloud: string; open: string }) {
  return (
    <tr className="border-t border-(--line)">
      <td className="px-2.5 py-1 text-left text-(--faint)">{label}</td>
      <td className="px-2.5 py-1 text-right">{cloud}</td>
      <td className="px-2.5 py-1 text-right text-(--ok)">{open}</td>
    </tr>
  );
}

function ModeBadge({ mode }: { mode?: string }) {
  if (mode === "cloud") {
    return (
      <span className="chip shrink-0 text-(--warn)" title="All four roles bill the cloud endpoint in this run">
        <ShieldAlert size={11} className="shrink-0" />
        cloud-only
      </span>
    );
  }
  if (mode === "hybrid") {
    return (
      <span className="chip shrink-0 text-(--ok)" title="Planner + reporter on the frontier endpoint, hands on open weights">
        <ShieldCheck size={11} className="shrink-0" />
        hybrid
      </span>
    );
  }
  return (
    <span className="chip shrink-0" title="Mode reported by the backend ledger">
      <Sparkles size={11} className="shrink-0" />
      ledger
    </span>
  );
}

export const PrivacyLedger = memo(PrivacyLedgerBase);
