"use client";

import { motion } from "framer-motion";
import { ShieldCheck, ShieldAlert, Sparkles } from "lucide-react";
import { memo } from "react";
import { fmtBytes, fmtCompact, fmtPct } from "@/lib/format";
import { SPRING } from "@/lib/motion";
import { privacyEqual, selectPrivacy } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { Panel, Ticker } from "./ui";
import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

function PrivacyHeroBase({ className }: { className?: string }) {
  const d = useNexus(selectPrivacy, privacyEqual);
  const leak = d.imagesOut > 0;
  const openPct = fmtPct(d.share);

  return (
    <Panel
      title="Privacy ledger"
      right={
        <span className={cn("chip", leak ? "text-(--warn)" : "text-(--ok)")}>
          <Sparkles size={12} />
          enforcement, not a promise
        </span>
      }
      className={cn("glass-hero lg:col-span-5", className)}
      enterIndex={1}
    >
      <RefractionEdge />
      <div className="flex h-full flex-col gap-4">
        <div className="flex items-center gap-4">
          <ShieldBadge leak={leak} />
          <div className="min-w-0">
            <div className="flex flex-wrap items-baseline gap-x-2">
              <Ticker
                value={d.imagesOut}
                className={cn("text-4xl font-bold tracking-tight", leak ? "text-(--warn)" : "text-(--text)")}
              />
              <span
                className={cn(
                  "text-[17px] font-semibold leading-tight",
                  leak ? "text-(--warn)" : "text-(--text)"
                )}
              >
                {leak ? "images sent to cloud" : "screenshots sent to cloud"}
              </span>
            </div>
            <p className="mt-1 text-[12.5px] leading-snug text-(--dim)">
              Every frame the executor sees stays on open weights — enforced by the ledger, not by convention.
            </p>
          </div>
        </div>

        <div>
          <div className="flex h-3.5 gap-1 overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${Math.max(d.share * 100, d.share > 0 ? 2.5 : 0)}%` }}
              transition={SPRING}
              className="rounded-full bg-gradient-to-r from-(--ok) to-(--cyan)"
            />
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${(1 - d.share) * 100}%` }}
              transition={SPRING}
              className={cn(
                "rounded-full bg-gradient-to-r from-(--violet)/70 to-(--run)/70",
                "lg:min-w-[2px]"
              )}
            />
          </div>
          <p className="mt-2 text-[13px] text-(--dim)">
            <span className="font-semibold text-(--ok)">{openPct}</span>{" "}
            <span className="font-medium text-(--text)">of tokens stayed on open weights</span>{" "}
            <span className="num">{`(${fmtCompact(d.openTokens)} open · ${fmtCompact(d.cloudTokens)} cloud)`}</span>
          </p>
        </div>

        <div className="grid flex-1 grid-cols-2 gap-3">
          <BucketCard
            name="Cloud (Spark)"
            role="planner · reporter"
            dot="var(--violet)"
            calls={d.cloudCalls}
            tokens={d.cloudTokens}
            bytes={d.cloudBytes}
          />
          <BucketCard
            name="Open weights"
            role="executor · verifier"
            dot="var(--ok)"
            calls={d.openCalls}
            tokens={d.openTokens}
            bytes={d.openBytes}
          />
        </div>

        <p className="caption flex items-center gap-2 normal-case! tracking-[0.02em]!">
          <Sparkles size={13} className="shrink-0 text-(--violet)" />
          Frontier model consulted {d.plannerCalls}× for {d.steps} {d.steps === 1 ? "step" : "steps"}
        </p>
      </div>
    </Panel>
  );
}

function ShieldBadge({ leak }: { leak: boolean }) {
  return (
    <motion.div
      className={cn(
        "grid h-[66px] w-[66px] shrink-0 place-items-center rounded-[22px] border transition-colors",
        leak ? "border-(--warn)/40 bg-(--warn)/15 text-(--warn)" : "border-(--ok)/35 bg-(--ok)/12 text-(--ok)"
      )}
      animate={leak ? { scale: [1, 1.04, 1] } : {}}
      transition={{ duration: 1.2, repeat: leak ? Infinity : 0 }}
    >
      {leak ? <ShieldAlert size={30} strokeWidth={1.8} /> : <ShieldCheck size={30} strokeWidth={1.8} />}
    </motion.div>
  );
}

function BucketCard({
  name,
  role,
  dot,
  calls,
  tokens,
  bytes,
}: {
  name: string;
  role: string;
  dot: string;
  calls: number;
  tokens: number;
  bytes: number;
}) {
  return (
    <div className="fill flex flex-col gap-2 p-3">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: dot }} />
        <span className="text-[12.5px] font-semibold text-(--text)">{name}</span>
        <span className="caption ml-auto text-[9px]!">{role}</span>
      </div>
      <div className="grid grid-cols-3 gap-1.5 text-center">
        <MiniStat label="tokens">
          <Ticker value={tokens} format={fmtCompact} className="text-[13px] font-semibold text-(--text)" />
        </MiniStat>
        <MiniStat label="bytes">
          <Ticker value={bytes} format={fmtBytes} className="text-[13px] font-semibold text-(--text)" />
        </MiniStat>
        <MiniStat label="calls">
          <Ticker value={calls} className="text-[13px] font-semibold text-(--text)" />
        </MiniStat>
      </div>
    </div>
  );
}

function MiniStat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-[10px] bg-(--fill-strong) px-1.5 py-1.5">
      {children}
      <div className="caption mt-0.5 text-[9px]!">{label}</div>
    </div>
  );
}

/** Decorative prism edge (SVG feDisplacementMap). Chromium renders the
 * displacement; other engines just get a soft gradient bar. */
function RefractionEdge() {
  return (
    <motion.div
      aria-hidden="true"
      className="pointer-events-none absolute -bottom-px left-8 right-8 h-px"
      style={{ filter: "url(#nexus-refraction)" }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 0.6 }}
      transition={{ duration: 1.2 }}
    >
      <div className="h-full bg-gradient-to-r from-transparent via-(--cyan) to-transparent" />
    </motion.div>
  );
}

export const PrivacyHero = memo(PrivacyHeroBase);
