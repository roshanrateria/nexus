"use client";

/** Ambient layer: drifting gradient blobs (transform-only keyframes) +
 * SVG grain. The refraction filter used by the privacy hero edge is defined
 * once here. */
export function Background() {
  return (
    <>
      <div className="bg-blobs" aria-hidden="true">
        <div className="blob blob-1" />
        <div className="blob blob-2" />
        <div className="blob blob-3" />
        <div className="blob blob-4" />
      </div>
      <div className="grain" aria-hidden="true" />
      <svg width="0" height="0" className="absolute" aria-hidden="true">
        <filter id="nexus-refraction" x="-8%" y="-8%" width="116%" height="116%">
          <feTurbulence type="fractalNoise" baseFrequency="0.012 0.05" numOctaves="2" seed="7" result="noise" />
          <feDisplacementMap in="SourceGraphic" in2="noise" scale="16" xChannelSelector="R" yChannelSelector="G" />
        </filter>
      </svg>
    </>
  );
}
