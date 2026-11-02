"use client";

import { useRef, useSyncExternalStore } from "react";
import { store, type StoreState } from "./store";
import { shallowEqual } from "./equal";

/** Selector-based external store subscription. The returned snapshot is
 * cached against the provided equality function, so identical content never
 * triggers a panel re-render even when SSE re-sends the full state. */
export function useNexus<T>(
  selector: (state: StoreState) => T,
  isEqual: (a: T, b: T) => boolean = shallowEqual
): T {
  const cacheRef = useRef<{ value: T; selector: (state: StoreState) => T } | null>(
    null
  );

  const getSnapshot = (): T => {
    if (!cacheRef.current || cacheRef.current.selector !== selector) {
      const fresh = selector(store.getState());
      cacheRef.current = { value: fresh, selector };
      return fresh;
    }
    const next = selector(store.getState());
    if (isEqual(cacheRef.current.value, next)) return cacheRef.current.value;
    cacheRef.current = { value: next, selector };
    return next;
  };

  return useSyncExternalStore(store.subscribe, getSnapshot, getSnapshot);
}
