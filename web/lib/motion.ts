"use client";

import { useReducedMotion } from "framer-motion";
import type { Transition } from "framer-motion";

/** Spring per spec: stiffness 300, damping 30. Reduced motion swaps to a
 * short fade. */
export const SPRING: Transition = { type: "spring", stiffness: 300, damping: 30 };

export function useEnter(enter?: Transition, delay = 0): Transition {
  const reduced = useReducedMotion();
  if (reduced) return { duration: 0.2, delay };
  return { ...(enter ?? SPRING), delay };
}

export function useListEnter(): Transition {
  return useEnter({ y: { type: "spring", stiffness: 300, damping: 30 }, opacity: { duration: 0.25 } });
}
