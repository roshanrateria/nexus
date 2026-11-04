"use client";

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type StageTab = "live" | "report" | "graph";

interface StageContextValue {
  tab: StageTab;
  setTab: (tab: StageTab) => void;
  goLive: () => void;
}

const StageContext = createContext<StageContextValue | null>(null);

/** Owns which center-stage tab is open (Live / Report / Graph) so any panel
 * can drive the stage — sites rows pin frames and jump to Live, the report
 * auto-opens while streaming. */
export function StageProvider({ children }: { children: ReactNode }) {
  const [tab, setTab] = useState<StageTab>("live");
  const goLive = useCallback(() => setTab("live"), []);
  const value = useMemo<StageContextValue>(() => ({ tab, setTab, goLive }), [tab, goLive]);
  return <StageContext.Provider value={value}>{children}</StageContext.Provider>;
}

export function useStage(): StageContextValue {
  const ctx = useContext(StageContext);
  if (!ctx) throw new Error("useStage must be used inside <StageProvider>");
  return ctx;
}
