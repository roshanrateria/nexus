"use client";

import { useEffect, useRef, type RefObject } from "react";

/** Sets --mx/--my on any glass card from the pointer position so the
 * `.glass::after` specular highlight follows the cursor. */
export function useSpecular<T extends HTMLElement>(): RefObject<T | null> {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const move = (e: PointerEvent): void => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${e.clientX - r.left}px`);
      el.style.setProperty("--my", `${e.clientY - r.top}px`);
    };
    el.addEventListener("pointermove", move, { passive: true });
    return () => {
      el.removeEventListener("pointermove", move);
    };
  }, []);
  return ref;
}
