"use client";

import { useEffect, useRef, useState, memo } from "react";
import { motion } from "framer-motion";
import { ExternalLink, MousePointerClick, RadioTower } from "lucide-react";
import { shotUrl } from "@/lib/urls";
import { eyeEqual, selectEye } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { cn } from "@/lib/cn";
import { Panel } from "./ui";
import { EmptyState } from "./EmptyState";

function BrowserEyeBase({ className }: { className?: string }) {
  const eye = useNexus(selectEye, eyeEqual);
  const url = shotUrl(eye.shot);
  const [shotKey, setShotKey] = useState(0);
  const prevShot = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (eye.shot !== prevShot.current) {
      prevShot.current = eye.shot;
      setShotKey((k) => k + 1);
    }
  }, [eye.shot]);

  const domain = (() => {
    if (!eye.url) return "";
    try {
      return new URL(eye.url).host;
    } catch {
      return eye.url.slice(0, 40);
    }
  })();

  return (
    <Panel
      title="Browser eye"
      right={
        <div className="flex items-center gap-1.5">
          {eye.iteration !== undefined && <span className="chip num">frame #{eye.iteration}</span>}
          {eye.url && (
            <a
              href={eye.url}
              target="_blank"
              rel="noopener noreferrer"
              className="icon-btn h-[26px] w-[26px] rounded-lg"
              aria-label="Open the current page in a new tab"
              title="Open current page"
            >
              <ExternalLink size={13} />
            </a>
          )}
        </div>
      }
      className={cn("lg:col-span-4", className)}
      enterIndex={3}
    >
      <div className="flex h-full min-h-0 flex-col gap-2">
        <ShotFrame src={url} shotKey={shotKey} />
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {domain ? (
            <span className="chip min-w-0">
              <RadioTower size={11} className="shrink-0" />
              <span className="truncate font-mono" title={eye.url}>
                {domain}
              </span>
            </span>
          ) : (
            <span className="chip">
              <RadioTower size={11} />
              no page yet
            </span>
          )}
          {eye.lastAction && (
            <span className="chip min-w-0">
              <MousePointerClick size={11} className="shrink-0 text-(--run)" />
              <span className="truncate font-mono text-[10.5px]" title={eye.lastAction}>
                {eye.lastAction}
              </span>
            </span>
          )}
        </div>
        {eye.title && (
          <p className="truncate text-[12px] text-(--dim)" title={eye.title}>
            {eye.title}
          </p>
        )}
      </div>
    </Panel>
  );
}

function ShotFrame({ src, shotKey }: { src: string | null; shotKey: number }) {
  const lastSrc = useRef<string | null>(null);
  const [fading, setFading] = useState<string | null>(null);

  useEffect(() => {
    if (src && src !== lastSrc.current) {
      setFading(lastSrc.current);
      lastSrc.current = src;
      const t = window.setTimeout(() => setFading(null), 700);
      return () => window.clearTimeout(t);
    }
    return undefined;
  }, [src]);

  if (!src) {
    return (
      <div className="fill-strong relative flex min-h-[170px] flex-1 items-center justify-center overflow-hidden rounded-[20px] bg-[#0a0f1a]/70">
        <EmptyState inFrame />
      </div>
    );
  }

  return (
    <div className="fill-strong relative min-h-[170px] flex-1 overflow-hidden rounded-[20px] bg-[#0a0f1a]/70">
      {fading && (
        <img src={fading} alt="" className="absolute inset-0 h-full w-full object-cover object-top" />
      )}
      <motion.img
        key={shotKey}
        src={src}
        alt="Latest browser frame"
        className="absolute inset-0 h-full w-full object-cover object-top"
        initial={{ opacity: 0, scale: 1.025 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.55, ease: "easeOut" }}
      />
      {shotKey > 0 && <ScanPass key={`scan-${shotKey}`} />}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 h-14 bg-gradient-to-t from-[rgb(4_6_12/.55)] to-transparent"
      />
    </div>
  );
}

/** One-pass scan-line sweep after each new frame; it ends out of frame, so
 * no cleanup is needed. */
function ScanPass() {
  return (
    <motion.div
      aria-hidden="true"
      className="scan"
      initial={{ y: "-110%" }}
      animate={{ y: "340%" }}
      transition={{ duration: 1.05, ease: "easeInOut" }}
    />
  );
}

export const BrowserEye = memo(BrowserEyeBase);
