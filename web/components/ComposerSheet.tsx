"use client";

import { useEffect, type ReactNode } from "react";
import { motion } from "framer-motion";
import { X } from "lucide-react";
import { SPRING, useEnter } from "@/lib/motion";
import { IconButton } from "./ui";

/** Centered glass sheet hosting composer-style content (New run). Esc or a
 * click on the backdrop closes it. */
export function ComposerSheet({
  title,
  children,
  onClose,
  className,
}: {
  title?: string;
  children?: ReactNode;
  onClose: () => void;
  className?: string;
}) {
  const enter = useEnter(SPRING);

  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey, true); // capture: wins over component-level Escape handlers
    return () => window.removeEventListener("keydown", onKey, true);
  }, [onClose]);

  return (
    <motion.div
      className="fixed inset-0 z-[60]"
      initial={{ opacity: 1 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
    >
      <motion.div
        className="absolute inset-0 bg-[rgb(4_6_12/.6)]"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 1 }}
        transition={{ duration: 0.2 }}
        onClick={onClose}
        aria-hidden="true"
      />
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        initial={{ opacity: 0, y: 26, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 18, scale: 0.97 }}
        transition={enter}
        className={`glass absolute left-1/2 top-1/2 w-[min(680px,92vw)] -translate-x-1/2 -translate-y-1/2 p-5 ${className ?? ""}`}
      >
        <header className="mb-2 flex shrink-0 items-center justify-between gap-3">
          {title && <h2 className="caption">{title}</h2>}
          <IconButton label="Close" onClick={onClose} className="ml-auto">
            <X size={15} />
          </IconButton>
        </header>
        {children}
      </motion.div>
    </motion.div>
  );
}
