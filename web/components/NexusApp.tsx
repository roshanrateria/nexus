"use client";

import { useEffect } from "react";
import { selectEvidences } from "@/lib/selectors";
import { evidencesEqual, stringsEqual } from "@/lib/equal";
import { useNexus } from "@/lib/useNexus";
import { store } from "@/lib/store";
import { statusInfo } from "@/lib/statusMap";
import { FramesProvider } from "@/lib/frames";
import { StageProvider } from "@/lib/stage";
import { Background } from "./Background";
import { Header } from "./Header";
import { StatStrip } from "./StatStrip";
import { SseBanner } from "./SseBanner";
import { PlanTimeline } from "./PlanTimeline";
import { SitesVisited } from "./SitesVisited";
import { CenterColumn } from "./CenterColumn";
import { PrivacyLedger } from "./PrivacyLedger";
import { EvidenceList } from "./EvidenceList";
import { Toasts } from "./Toasts";
import { EvidenceSheetProvider } from "./EvidenceSheet";
import { GlassRegion } from "./ui";

const selectStatus = (s: Parameters<typeof selectEvidences>[0]) => s.data?.status ?? "";
const selectGoalString = (s: Parameters<typeof selectEvidences>[0]) => s.data?.goal ?? "";

/** Document title mirrors the run status, e.g. “Running — Nexus”. */
function useRunDocTitle(): void {
  const status = useNexus(selectStatus, stringsEqual);
  const goal = useNexus(selectGoalString, stringsEqual);
  useEffect(() => {
    if (!goal && !status) {
      document.title = "Nexus";
      return;
    }
    document.title = `${statusInfo(status, "").label} — Nexus`;
  }, [status, goal]);
}

export function NexusApp() {
  const evidences = useNexus(selectEvidences, evidencesEqual);
  useRunDocTitle();

  /** Demo mode boots the scripted replay instead of the SSE stream. */
  useEffect(() => {
    if (new URLSearchParams(window.location.search).has("demo")) {
      store.startDemo();
    } else {
      store.connect();
    }
    // One-shot bootstrap; the store owns reconnects from here on.
  }, []);

  return (
    <EvidenceSheetProvider evidences={evidences}>
      <StageProvider>
        <FramesProvider>
          <Background />
          <SseBanner />

          <main className="nexus-shell" data-testid="nexus-shell">
            <Header />
            <StatStrip />

            {/* left: plan + sites */}
            <GlassRegion className="flex flex-col gap-3 p-3">
              <PlanTimeline className="nexus-pane min-h-0 flex-[1.4] p-3!" />
              <SitesVisited className="nexus-pane min-h-0 flex-1 p-3!" />
            </GlassRegion>

            {/* center: live / report / graph stage + activity ticker */}
            <CenterColumn className="nexus-region glass nexus-stage p-3" />

            {/* right: privacy ledger + evidence */}
            <GlassRegion className="flex flex-col gap-3 p-3">
              <PrivacyLedger className="nexus-pane" />
              <EvidenceList className="nexus-pane min-h-0 flex-1" />
            </GlassRegion>
          </main>

          <Toasts />
        </FramesProvider>
      </StageProvider>
    </EvidenceSheetProvider>
  );
}

/* The shell owns exactly five backdrop-filter surfaces (header, stat strip,
 * left column, center stage, right column); everything inside is a plain
 * translucent `.fill`. JSX mirrors the `nexus-shell` grid rows (header 56 /
 * strip 76 / columns 1fr). */
