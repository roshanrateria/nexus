"use client";

import { useEffect } from "react";
import { selectEvidences } from "@/lib/selectors";
import { evidencesEqual, stringsEqual } from "@/lib/equal";
import { useNexus } from "@/lib/useNexus";
import { store } from "@/lib/store";
import { Background } from "./Background";
import { Header } from "./Header";
import { PrivacyHero } from "./PrivacyHero";
import { BrowserEye } from "./BrowserEye";
import { ActivityFeed } from "./ActivityFeed";
import { PlanTimeline } from "./PlanTimeline";
import { EvidenceCards } from "./EvidenceCards";
import { KnowledgeGraph } from "./KnowledgeGraph";
import { ReportPanel } from "./ReportPanel";
import { Toasts } from "./Toasts";
import { EmptyState } from "./EmptyState";
import { MissionComposer } from "./MissionComposer";
import { EvidenceSheetProvider } from "./EvidenceSheet";

const selectGoalString = (s: Parameters<typeof selectEvidences>[0]) => s.data?.goal ?? "";

export function NexusApp() {
  const goal = useNexus(selectGoalString, stringsEqual);
  const evidences = useNexus(selectEvidences, evidencesEqual);

  /** Demo mode boots the scripted replay instead of the SSE stream. */
  useEffect(() => {
    if (new URLSearchParams(window.location.search).has("demo")) {
      store.startDemo();
    } else {
      store.connect();
    }
    // One-shot bootstrap; the store owns reconnects from here on.
  }, []);

  useEffect(() => {
    if (goal) document.title = `Nexus — ${goal.slice(0, 64)}`;
  }, [goal]);

  return (
    <EvidenceSheetProvider evidences={evidences}>
      <Background />
      <main className="mx-auto grid w-full max-w-[1560px] grid-cols-1 gap-3.5 p-3.5 md:grid-cols-2 md:p-5 lg:grid-cols-12">
        <Header />
        {goal ? (
          <>
            <PrivacyHero className="md:col-span-2 lg:col-span-5" />
            <BrowserEye className="md:col-span-1 lg:col-span-4" />
            <ActivityFeed className="md:col-span-1" />
            <PlanTimeline className="md:col-span-2 lg:col-span-5" />
            <EvidenceCards className="md:col-span-2 lg:col-span-4" />
            <KnowledgeGraph className="md:col-span-2 lg:col-span-4" />
            <ReportPanel className="md:col-span-2 lg:col-span-8" />
            {/* Docked composer: queue another goal / cancel while a run is live. */}
            <MissionComposer docked />
          </>
        ) : (
          <EmptyState withComposer className="md:col-span-2 py-10 md:py-14 lg:col-span-12" />
        )}
      </main>
      <Toasts />
    </EvidenceSheetProvider>
  );
}
