"use client";

import { memo, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Lock, MousePointerClick } from "lucide-react";
import { eyeEqual, selectEye } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { shotUrl, splitUrl } from "@/lib/urls";
import { useFrames, type Frame } from "@/lib/frames";
import { useEnter } from "@/lib/motion";
import { cn } from "@/lib/cn";
import { EmptyFrame } from "./EmptyState";

/** The live browser stage: chrome bar with URL pill + page title, the
 * aspect-preserved screenshot, filmstrip and action HUD. */
function BrowserWindowBase({ className }: { className?: string }) {
  const eye = useNexus(selectEye, eyeEqual);
  const running = eye.status === "running" || eye.status === "reporting";
  const { frames, latest, pinnedFrame, pinnedIndex, pin, returnToLive } = useFrames();

  const shown = pinnedFrame ?? latest;
  const src = shotUrl(shown?.shot) ?? null;

  return (
    <div className={cn("fill flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden p-2.5", className)}>
      <ChromeBar
        url={shown?.url ?? eye.url}
        title={shown?.title ?? eye.title}
        running={running && !pinnedFrame}
      />

      <ShotStage src={src}>
        <LiveBadge
          frames={frames}
          pinned={pinnedIndex}
          frameNumber={shown?.iteration}
          onReturn={returnToLive}
        />
        {eye.lastAction && (
          <div className="pointer-events-none absolute bottom-3 left-3 z-10 flex max-w-[85%] items-center gap-2 rounded-full border border-(--line) bg-[rgb(4_6_12/.8)] px-3 py-1.5 backdrop-blur-sm">
            <MousePointerClick size={11} className="shrink-0 text-(--run)" />
            <span className="truncate font-mono text-[11px] text-(--text)" title={eye.lastAction}>
              {eye.lastAction}
            </span>
          </div>
        )}
      </ShotStage>

      <Filmstrip frames={frames} pinned={pinnedIndex} onPin={pin} />
    </div>
  );
}

/* --------------------------------------------------------------- chrome */

function ChromeBar({ url, title, running }: { url?: string; title?: string; running: boolean }) {
  const { host, path } = useMemo(() => splitUrl(url), [url]);
  return (
    <div className="mb-2.5 flex shrink-0 items-center gap-2 px-1 pt-0.5">
      <div className="flex shrink-0 items-center gap-1.5" aria-hidden="true">
        <span className="tomato bg-[#fb7185]" />
        <span className="tomato bg-[#fbbf24]" />
        <span className="tomato bg-[#34d399]" />
      </div>

      {/* page title as the active tab label */}
      <span
        className="chip max-w-[220px] shrink basis-0 overflow-hidden border-(--violet)/25 bg-(--violet)/10 text-(--text)"
        title={title || "Nexus browser"}
      >
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-(--violet)" />
        <span className="truncate text-[11px]">{title || "Nexus browser"}</span>
      </span>

      <span className="url-pill min-w-0 flex-1" title={url || "about:blank"}>
        <Lock size={10} className="shrink-0 text-(--ok)" />
        {host ? (
          <>
            <span className="shrink-0 font-semibold text-(--text)">{host}</span>
            {path && <span className="truncate text-(--dim)">{path}</span>}
          </>
        ) : (
          <span className="truncate text-(--faint)">about:blank</span>
        )}
      </span>

      {/* thin progress shimmer while the agent is mid-run */}
      {running && (
        <span aria-hidden="true" className="shimmer h-[3px] w-16 shrink-0 rounded-full opacity-80" />
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- shot */

interface Fit {
  w: number;
  h: number;
}

function fitInside(natural: { w: number; h: number }, box: { w: number; h: number }, pad = 8): Fit | null {
  if (!box.w || !box.h || !natural.w || !natural.h) return null;
  const scale = Math.min((box.w - pad * 2) / natural.w, (box.h - pad * 2) / natural.h);
  return {
    w: Math.max(1, Math.floor(natural.w * scale)),
    h: Math.max(1, Math.floor(natural.h * scale)),
  };
}

interface ShotLayer {
  src: string;
  natural: { w: number; h: number } | null;
  ready: boolean;
}

function ShotStage({ src, children }: { src: string | null; children?: ReactNode }) {
  const boxRef = useRef<HTMLDivElement | null>(null);
  const [box, setBox] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    const measure = (): void => setBox({ w: el.clientWidth, h: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div
      ref={boxRef}
      className="relative flex min-h-0 min-w-0 flex-1 items-center justify-center overflow-hidden rounded-[16px] border border-(--line) bg-[#05070e]"
      data-testid="browser-frame"
    >
      {src ? <LayeredShot src={src} box={box} /> : <EmptyShot measured={box.w > 0} />}
      {children}
    </div>
  );
}

/** Cross-fading stack of at most two frames; each image is given explicit
 * width/height from its natural size vs the measured box, so the picture is
 * never cropped or stretched — just letterboxed + centered. */
function LayeredShot({ src, box }: { src: string; box: { w: number; h: number } }) {
  const reduced = useReducedMotion();
  const [layers, setLayers] = useState<ShotLayer[]>([]);
  const layersRef = useRef<ShotLayer[]>([]);

  useEffect(() => {
    const list = layersRef.current;
    if (list.length && list[list.length - 1].src === src) return;
    if (!list.length || !list.some((l) => l.ready)) {
      const fresh: ShotLayer[] = [{ src, natural: null, ready: false }];
      layersRef.current = fresh;
      setLayers(fresh);
      return;
    }
    // Crossfade: keep the last loaded layer underneath for the handover.
    const under = list[list.length - 1];
    const next: ShotLayer[] = [{ ...under }, { src, natural: null, ready: false }];
    layersRef.current = next;
    setLayers(next);
  }, [src]);

  const loaded = (i: number, natural: { w: number; h: number }): void => {
    const list = layersRef.current;
    if (!list[i] || list[i].ready) return;
    const copy = [...list];
    copy[i] = { ...copy[i], natural, ready: true };
    layersRef.current = copy;
    setLayers(copy);
    // Retire older layers once the top frame is on screen.
    window.setTimeout(() => {
      const still = layersRef.current;
      const top = still[still.length - 1];
      if (still.length > 1 && top?.ready) {
        layersRef.current = [top];
        setLayers([top]);
      }
    }, 240);
  };

  const topReady = layers.length ? layers[layers.length - 1].ready : false;
  const topSrc = layers.length ? layers[layers.length - 1].src : null;
  const fade = { duration: reduced ? 0.01 : 0.15 };

  return (
    <>
      {layers.map((layer, i) => {
        const top = i === layers.length - 1;
        const fit = fitInside(layer.natural ?? { w: 0, h: 0 }, box);
        return (
          <motion.img
            key={layer.src}
            src={layer.src}
            alt="Observed browser frame"
            draggable={false}
            initial={{ opacity: 0 }}
            animate={{ opacity: top ? (layer.ready ? 1 : 0) : topReady ? 0 : 1 }}
            transition={fade}
            onLoad={(e) => {
              const img = e.currentTarget;
              if (img.naturalWidth && img.naturalHeight) loaded(i, { w: img.naturalWidth, h: img.naturalHeight });
            }}
            style={
              fit
                ? { width: fit.w, height: fit.h, position: "absolute", borderRadius: 8 }
                : { opacity: 0, position: "absolute" }
            }
          />
        );
      })}
      {topReady && <ScanSweep src={topSrc} />}
      {!topReady && <FrameSkeleton />}
    </>
  );
}

function FrameSkeleton() {
  // 16:10 placeholder sized to the box while the first frame loads.
  return (
    <div
      className="shimmer opacity-70"
      style={{ aspectRatio: "16 / 10", width: "min(92%, 620px)", maxWidth: "100%" }}
      aria-hidden="true"
    />
  );
}

function EmptyShot({ measured }: { measured: boolean }) {
  return (
    <div className="flex flex-col items-center gap-3 text-center">
      <motion.div
        animate={measured ? { y: [0, -4, 0] } : undefined}
        transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
      >
        <EmptyFrame />
      </motion.div>
      <p className="max-w-[300px] px-4 text-[12.5px] leading-snug text-(--dim)">
        Frames stream here the moment the agent opens its browser.
      </p>
    </div>
  );
}

/** One-pass scan-line sweep after each new frame; it always ends out of
 * frame, so no cleanup is needed. */
function ScanSweep({ src }: { src: string | null }) {
  return (
    <motion.div
      aria-hidden="true"
      className="scan"
      key={src ?? "scan"}
      initial={{ y: "-110%" }}
      animate={{ y: "340%" }}
      transition={{ duration: 1.05, ease: "easeInOut" }}
    />
  );
}

/* ---------------------------------------------------------------- badges */

function UpdatedAgo({ at }: { at: number }) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, []);
  const seconds = Math.max(0, Math.round((Date.now() - at) / 1000));
  return <span className="num">{seconds > 0 ? `${seconds}s ago` : "just now"}</span>;
}

function LiveBadge({
  frames,
  pinned,
  frameNumber,
  onReturn,
}: {
  frames: Frame[];
  pinned: number | null;
  frameNumber?: number;
  onReturn: () => void;
}) {
  const spark = frames[frames.length - 1];
  if (pinned !== null) {
    return (
      <button
        type="button"
        className="live-dot pointer-events-auto absolute left-3 top-3 z-10 cursor-pointer"
        data-paused="true"
        onClick={onReturn}
        title="Return to the live feed (L)"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-(--warn)" />
        Paused on frame {frameNumber ?? pinned + 1}
        <span className="font-normal opacity-75">— return to live</span>
      </button>
    );
  }
  if (!spark) return null;
  return (
    <span className="live-dot absolute left-3 top-3 z-10" data-paused="false">
      <span className="h-1.5 w-1.5 rounded-full bg-(--ok)" />
      LIVE
      <span className="num font-normal opacity-80">#{frameNumber ?? spark.iteration ?? spark.index}</span>
      <span className="num font-normal opacity-60">
        <UpdatedAgo at={spark.at} />
      </span>
    </span>
  );
}

/* ------------------------------------------------------------ filmstrip */

function Filmstrip({
  frames,
  pinned,
  onPin,
}: {
  frames: Frame[];
  pinned: number | null;
  onPin: (index: number) => void;
}) {
  const rowRef = useRef<HTMLDivElement | null>(null);
  const selected = pinned ?? frames.length - 1;
  const enter = useEnter({ duration: 0.18 });

  // Keep the selected thumb visible; never jump the page.
  useEffect(() => {
    const row = rowRef.current;
    if (!row || selected < 0) return;
    const child = row.children[selected] as HTMLElement | undefined;
    if (!child) return;
    const behavior: ScrollBehavior = "smooth";
    row.scrollTo({ left: Math.max(0, child.offsetLeft - 12), behavior });
  }, [selected, frames.length]);

  return (
    <div
      ref={rowRef}
      className="mt-2.5 flex h-[72px] shrink-0 items-center gap-2 overflow-x-auto pt-1 pb-1"
      role="listbox"
      aria-label="Frame filmstrip"
    >
      {frames.length === 0 ? (
        <div className="flex w-full items-center justify-center">
          <span className="text-[11.5px] text-(--faint)">The filmstrip fills as frames stream in.</span>
        </div>
      ) : (
        frames.map((frame, i) => {
          const url = shotUrl(frame.shot);
          const isSelected = i === selected;
          const isLiveEdge = i === frames.length - 1;
          return (
            <motion.button
              key={`${frame.iteration ?? frame.index}-${frame.shot}`}
              type="button"
              role="option"
              aria-selected={isSelected}
              aria-label={`Frame ${frame.iteration ?? frame.index}` + (frame.url ? ` · ${frame.url}` : "")}
              initial={{ opacity: 0, x: 14 }}
              animate={{ opacity: 1, x: 0 }}
              transition={enter}
              onClick={() => onPin(i)}
              className="film-thumb"
              data-pinned={isSelected}
              data-live-edge={isLiveEdge}
              title={frame.url ?? `Frame ${frame.iteration ?? frame.index}`}
            >
              {url && (
                <img
                  src={url}
                  alt=""
                  draggable={false}
                  className="h-full w-full object-cover object-top"
                  loading="lazy"
                />
              )}
              <span
                className="num absolute bottom-0 right-0 rounded-tl-[6px] bg-[rgb(4_6_12/.85)] px-1 text-[9px] font-semibold text-(--dim)"
                aria-hidden="true"
              >
                {frame.iteration ?? frame.index}
              </span>
            </motion.button>
          );
        })
      )}
    </div>
  );
}

export const BrowserWindow = memo(BrowserWindowBase);
