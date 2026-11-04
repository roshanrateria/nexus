"use client";

import { Check, Copy } from "lucide-react";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { AnimatePresence, motion, useSpring, useTransform, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/cn";
import { fmtInt } from "@/lib/format";
import { SPRING, useEnter } from "@/lib/motion";
import { TONE_COLOR, type StatusInfo } from "@/lib/statusMap";
import { useSpecular } from "@/lib/useSpecular";

/* ------------------------------------------------------------------ glass */

/** A glass region whose specular highlight tracks the pointer (--mx/--my
 * feed the `.glass::after` radial). */
export function GlassRegion({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  const ref = useSpecular<HTMLDivElement>();
  return (
    <div ref={ref} className={cn("nexus-region glass", className)}>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ logo */

export function LogoGlyph({ size = 30, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="nexus-glyph-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#818cf8" />
          <stop offset="1" stopColor="#22d3ee" />
        </linearGradient>
      </defs>
      <circle cx="16" cy="16" r="12.5" fill="none" stroke="url(#nexus-glyph-g)" strokeOpacity=".4" strokeWidth="1.5" />
      <path
        d="M10 21.5 L16 9.5 L22 21.5 Z"
        fill="none"
        stroke="url(#nexus-glyph-g)"
        strokeWidth="1.9"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx="10" cy="21.5" r="2.5" fill="#818cf8" />
      <circle cx="22" cy="21.5" r="2.5" fill="#22d3ee" />
      <motion.circle
        cx="16"
        cy="9.5"
        r="2.8"
        fill="url(#nexus-glyph-g)"
        animate={{ opacity: [1, 0.55, 1] }}
        transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
      />
    </svg>
  );
}

/* ------------------------------------------------------------- status dot */

export function StatusDot({ pulse, color }: { pulse?: boolean; color: string }) {
  return (
    <span className="relative flex h-2 w-2 shrink-0">
      {pulse && (
        <motion.span
          className="absolute inline-flex h-full w-full rounded-full"
          style={{ backgroundColor: color }}
          animate={{ opacity: [0.5, 0], scale: [1, 2.2] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "easeOut" }}
        />
      )}
      <span className="relative inline-flex h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
    </span>
  );
}

/* ------------------------------------------------------------------ pill */

export function StatusPill({ info, className }: { info: StatusInfo; className?: string }) {
  const color = TONE_COLOR[info.tone];
  return (
    <span className={cn("pill", className)} style={{ "--tone": color } as CSSProperties} data-testid="status-pill">
      <StatusDot pulse={info.pulse} color={color} />
      <span className="truncate">{info.label}</span>
    </span>
  );
}

/* ------------------------------------------------------------- tickers */

export function Ticker({
  value,
  format = fmtInt,
  className,
}: {
  value: number;
  format?: (n: number) => string;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const spring = useSpring(value, { stiffness: 300, damping: 30 });
  useEffect(() => {
    if (reduced) spring.jump(value);
    else spring.set(value);
  }, [value, spring, reduced]);
  const text = useTransform(spring, (v) => (reduced ? String(value) : format(v)));
  return (
    <motion.span className={cn("num", className)} style={{ display: "inline-block" }}>
      {text}
    </motion.span>
  );
}

/* ------------------------------------------------------------ magnetic */

export function Magnetic({ children, className }: { children: ReactNode; className?: string }) {
  const reduced = useReducedMotion();
  const x = useSpring(0, { stiffness: 300, damping: 30 });
  const y = useSpring(0, { stiffness: 300, damping: 30 });
  const ref = useRef<HTMLSpanElement>(null);
  return (
    <motion.span
      ref={ref}
      className={cn("inline-flex", className)}
      style={{ x, y }}
      onPointerMove={(e) => {
        if (reduced) return;
        const r = ref.current?.getBoundingClientRect();
        if (!r) return;
        const dx = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
        const dy = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
        x.set(Math.max(-1, Math.min(1, dx)) * 3.5);
        y.set(Math.max(-1, Math.min(1, dy)) * 2.5);
      }}
      onPointerLeave={() => {
        x.set(0);
        y.set(0);
      }}
    >
      {children}
    </motion.span>
  );
}

/* --------------------------------------------------- generic icon button */

interface IconButtonProps {
  label: string;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
  href?: string;
  title?: string;
}

export function IconButton({ label, onClick, children, className, href, title }: IconButtonProps) {
  const cls = cn("icon-btn", className);
  if (href) {
    return (
      <a className={cls} href={href} target="_blank" rel="noopener noreferrer" aria-label={label} title={title ?? label}>
        {children}
      </a>
    );
  }
  return (
    <button type="button" className={cls} onClick={onClick} aria-label={label} title={title ?? label}>
      {children}
    </button>
  );
}

/* ---------------------------------------------------------- copy button */

export function CopyButton({
  text,
  label = "Copy to clipboard",
  className,
  compact,
}: {
  text: string;
  label?: string;
  className?: string;
  compact?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);
  useEffect(() => () => void (timer.current !== null && clearTimeout(timer.current)), []);

  const copy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
      } finally {
        document.body.removeChild(ta);
      }
    }
    setCopied(true);
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(false), 1800);
  };

  return (
    <IconButton label={copied ? "Copied" : label} onClick={() => void copy()} className={className} title={label}>
      <span className="relative block h-[15px] w-[15px]">
        <AnimatePresence initial={false} mode="wait">
          {copied ? (
            <motion.span
              key="check"
              className="absolute inset-0 grid place-items-center text-(--ok)"
              initial={{ scale: 0.4, opacity: 0, rotate: -30 }}
              animate={{ scale: 1, opacity: 1, rotate: 0 }}
              exit={{ scale: 0.5, opacity: 0 }}
              transition={SPRING}
            >
              <Check size={15} />
            </motion.span>
          ) : (
            <motion.span
              key="copy"
              className="absolute inset-0 grid place-items-center"
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.6, opacity: 0 }}
              transition={{ duration: 0.15 }}
            >
              <Copy size={compact ? 13 : 15} />
            </motion.span>
          )}
        </AnimatePresence>
      </span>
    </IconButton>
  );
}

/* ------------------------------------------------------------------ panel */

export interface PanelProps {
  title?: string;
  /** Number shown in a small count badge next to the title. */
  count?: number | string;
  action?: ReactNode;
  className?: string;
  bodyClassName?: string;
  /** Body scrolls internally (thin scrollbar); false for auto content. */
  scroll?: boolean;
  /** data-testid hook for E2E checks; attribute only, no styling. */
  testId?: string;
  children: ReactNode;
}

export function Panel({ title, count, action, className, bodyClassName, scroll = true, testId, children }: PanelProps) {
  const hasHeader = Boolean(title) || count !== undefined || Boolean(action);
  return (
    <section data-testid={testId} className={cn("fill relative flex min-h-0 min-w-0 flex-col overflow-hidden p-4", className)}>
      {hasHeader && (
        <header className="mb-3 flex shrink-0 items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            {title && <h2 className="caption truncate">{title}</h2>}
            {count !== undefined && <CountBadge value={count} />}
          </div>
          {action}
        </header>
      )}
      <div className={cn("flex min-h-0 flex-1 flex-col", scroll && "scroll overflow-y-auto", bodyClassName)}>
        {children}
      </div>
    </section>
  );
}

export function CountBadge({ value, className }: { value: number | string; className?: string }) {
  return (
    <span className={cn("chip num shrink-0 px-2 py-0 text-[10.5px]!", className)}>{value}</span>
  );
}

/** Friendly empty body for a panel. */
export function PanelEmpty({ icon, title, hint }: { icon: ReactNode; title: string; hint?: string }) {
  return (
    <div className="flex h-full min-h-[120px] flex-col items-center justify-center gap-2 px-6 text-center">
      <span className="text-(--faint)">{icon}</span>
      <p className="text-[13px] leading-snug text-(--dim)">{title}</p>
      {hint && <p className="max-w-[280px] text-[11.5px] leading-snug text-(--faint)">{hint}</p>}
    </div>
  );
}

/* ------------------------------------------------------------------ segmented */

export interface SegOption {
  id: string;
  label: string;
  hotkey?: string;
  /** data-testid hook for E2E checks; attribute only, no styling. */
  testId?: string;
}

export function Segmented({
  options,
  value,
  onChange,
  className,
}: {
  options: SegOption[];
  value: string;
  onChange: (id: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("seg", className)} role="tablist" aria-label="Center view">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          role="tab"
          data-active={option.id === value}
          data-testid={option.testId}
          aria-selected={option.id === value}
          onClick={() => onChange(option.id)}
          title={option.hotkey ? `${option.label} (${option.hotkey})` : option.label}
          className="seg-btn"
        >
          {option.label}
          {option.hotkey && <kbd className="seg-key">{option.hotkey}</kbd>}
        </button>
      ))}
    </div>
  );
}

/* --------------------------------------------------------------- buttons */

export function GhostButton({
  children,
  onClick,
  className,
}: {
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <motion.button
      type="button"
      whileHover={{ y: -1 }}
      whileTap={{ scale: 0.97 }}
      transition={SPRING}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-2 rounded-[12px] border px-4 py-2 text-[13px] font-medium transition-colors",
        "border-(--line) bg-(--fill) hover:bg-(--fill-strong)",
        className
      )}
    >
      {children}
    </motion.button>
  );
}

/* ------------------------------------------------------------------ enter */

export { useEnter, SPRING };
