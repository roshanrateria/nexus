"use client";

import { memo, type ReactNode } from "react";
import { BadgeCheck, Globe2, Sparkles, Wallet, Workflow } from "lucide-react";
import { statsEqual, selectStats, type Stats } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { fmtCost, fmtInt } from "@/lib/format";
import { Ticker } from "./ui";

/** Strip of five mission metrics under the header. */
function StatStripBase() {
  const s = useNexus(selectStats, statsEqual);

  return (
    <section
      className="glass col-span-full grid min-h-0 grid-cols-3 gap-3 px-3 py-2.5 nd:grid-cols-5"
      aria-label="Run metrics"
    >
      <StepStat values={s} />
      <StatCard icon={<Globe2 size={12} />} label="Sites visited">
        <Ticker value={s.sites} className="text-[20px] font-semibold leading-none text-(--text)" />
      </StatCard>
      <StatCard icon={<BadgeCheck size={12} />} label="Evidence">
        <Ticker value={s.evidenceCount} className="text-[20px] font-semibold leading-none text-(--text)" />
      </StatCard>
      <StatCard icon={<Sparkles size={12} />} label="Escalations">
        <Ticker value={s.escalations} className="text-[20px] font-semibold leading-none text-(--text)" />
      </StatCard>
      <CostStat cost={s.costUsd} />
    </section>
  );
}

function StepStat({ values }: { values: Stats }) {
  const total = values.historyLen + values.planLen;
  return (
    <StatCard icon={<Workflow size={12} />} label="Step">
      {total > 0 ? (
        <span className="num flex items-baseline gap-1 text-(--text)">
          <Ticker value={values.historyLen} className="text-[20px] font-semibold leading-none" />
          <span className="text-[12.5px] font-semibold text-(--dim)">/ {fmtInt(total)}</span>
        </span>
      ) : (
        <span className="text-[20px] font-semibold leading-none text-(--faint)">–</span>
      )}
    </StatCard>
  );
}

function CostStat({ cost }: { cost: number | null }) {
  return (
    <StatCard icon={<Wallet size={12} />} label="Cost" testId="stat-cost">
      {cost === null || cost === undefined ? (
        <span className="text-[20px] font-semibold leading-none text-(--faint)">n/a</span>
      ) : (
        <Ticker value={cost} format={fmtCost} className="text-[20px] font-semibold leading-none text-(--text)" />
      )}
    </StatCard>
  );
}

function StatCard({
  icon,
  label,
  testId,
  children,
}: {
  icon: ReactNode;
  label: string;
  testId?: string;
  children: ReactNode;
}) {
  return (
    <div className="fill flex min-w-0 flex-col justify-center gap-1.5 px-3.5 py-2" data-testid={testId}>
      <span className="caption flex items-center gap-1.5 text-[9.5px]!">
        {icon}
        {label}
      </span>
      {children}
    </div>
  );
}

export const StatStrip = memo(StatStripBase);
