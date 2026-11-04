"use client";

import { LogoGlyph } from "./ui";

/** The brand glyph used in friendly empty states (browser stage, panels). */
export function EmptyFrame({ size = 40, label }: { size?: number; label?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <LogoGlyph size={size} />
      {label && <p className="text-[12.5px] text-(--dim)">{label}</p>}
    </div>
  );
}
