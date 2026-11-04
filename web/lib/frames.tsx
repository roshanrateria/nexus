"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { eyeEqual, selectEye } from "./selectors";
import { useNexus } from "./useNexus";

/** One browser frame observed from the agent (the filmstrip + browser
 * window are both driven from this list). */
export interface Frame {
  /** 1-based position in the strip. */
  index: number;
  /** Raw shot reference from the backend (resolve with shotUrl). */
  shot: string;
  url?: string;
  title?: string;
  /** Backend frame counter (`current.iteration`); falls back to index. */
  iteration?: number;
  /** Client arrival time, for the "updated Ns ago" badge. */
  at: number;
}

interface FramesContextValue {
  frames: Frame[];
  latest: Frame | null;
  /** Index into frames, or null when following live. */
  pinnedIndex: number | null;
  pinnedFrame: Frame | null;
  pin: (index: number) => void;
  pinUrl: (url: string) => boolean;
  returnToLive: () => void;
}

const FramesContext = createContext<FramesContextValue | null>(null);

/** Accumulates every distinct observed frame (deduped by shot/url/iteration,
 * in arrival order) and owns frame pinning. Resets when the run changes. */
export function FramesProvider({ children }: { children: ReactNode }) {
  const eye = useNexus(selectEye, eyeEqual);
  const [frames, setFrames] = useState<Frame[]>([]);
  const [pinnedIndex, setPinnedIndex] = useState<number | null>(null);
  const eyeRef = useRef<typeof eye | null>(null);
  const framesRef = useRef<Frame[]>([]);

  useEffect(() => {
    const prev = eyeRef.current;
    eyeRef.current = eye;

    // New run: wipe the strip and drop any pin, then keep pushing frames.
    if (prev && prev.runId !== eye.runId) {
      setPinnedIndex(null);
      framesRef.current = [];
      setFrames([]);
    }
    if (!eye.shot || !eye.iteration) return;

    const last = framesRef.current[framesRef.current.length - 1];
    const seen = last && last.shot === eye.shot && last.url === eye.url && last.iteration === eye.iteration;
    if (seen) return;
    const frame: Frame = {
      index: framesRef.current.length + 1,
      shot: eye.shot,
      url: eye.url,
      title: eye.title,
      iteration: eye.iteration,
      at: Date.now(),
    };
    const next = [...framesRef.current, frame];
    framesRef.current = next;
    setFrames(next);
  }, [eye]);

  const pin = useCallback((index: number) => {
    setPinnedIndex((current) => (current === index ? null : index));
  }, []);

  const pinUrl = useCallback((url: string): boolean => {
    const list = framesRef.current;
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].url === url) {
        setPinnedIndex(i);
        return true;
      }
    }
    // Fallback: same origin + path (query stripped both sides).
    const normalize = (u: string): string => {
      try {
        const parsed = new URL(u);
        return `${parsed.host}${parsed.pathname}`;
      } catch {
        return u;
      }
    };
    const needle = normalize(url);
    for (let i = list.length - 1; i >= 0; i--) {
      if (list[i].url && normalize(list[i].url as string) === needle) {
        setPinnedIndex(i);
        return true;
      }
    }
    return false;
  }, []);

  // Backend resets mid-run (error / cancel) — if the frames list vanishes
  // while pinned, fall back to live rather than a dead index.
  useEffect(() => {
    if (pinnedIndex !== null && pinnedIndex >= frames.length) setPinnedIndex(null);
  }, [frames.length, pinnedIndex]);

  const returnToLive = useCallback(() => setPinnedIndex(null), []);

  const value = useMemo<FramesContextValue>(() => {
    const latest = frames.length ? frames[frames.length - 1] : null;
    return {
      frames,
      latest,
      pinnedIndex,
      pinnedFrame: pinnedIndex !== null && pinnedIndex < frames.length ? frames[pinnedIndex] : null,
      pin,
      pinUrl,
      returnToLive,
    };
  }, [frames, pinnedIndex, pin, pinUrl, returnToLive]);

  return <FramesContext.Provider value={value}>{children}</FramesContext.Provider>;
}

export function useFrames(): FramesContextValue {
  const ctx = useContext(FramesContext);
  if (!ctx) throw new Error("useFrames must be used inside <FramesProvider>");
  return ctx;
}
