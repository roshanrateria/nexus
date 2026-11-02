"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useEnter } from "@/lib/motion";
import { IconButton } from "./ui";
import { SPRING } from "@/lib/motion";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const current = document.documentElement.dataset.theme;
    if (current === "light" || current === "dark") setTheme(current);
  }, []);

  const toggle = (): void => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("nexus-theme", next);
    } catch {
      /* private mode: theme simply won't persist */
    }
  };

  const enter = useEnter(SPRING);
  return (
    <IconButton label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} onClick={toggle}>
      <span className="relative block h-[15px] w-[15px]">
        <AnimatePresence initial={false} mode="wait">
          <motion.span
            key={theme}
            className="absolute inset-0 grid place-items-center"
            initial={{ scale: 0.3, opacity: 0, rotate: theme === "light" ? 90 : -90 }}
            animate={{ scale: 1, opacity: 1, rotate: 0 }}
            exit={{ scale: 0.3, opacity: 0, rotate: theme === "light" ? -90 : 90 }}
            transition={enter}
          >
            {theme === "dark" ? <Sun size={15} /> : <Moon size={15} />}
          </motion.span>
        </AnimatePresence>
      </span>
    </IconButton>
  );
}
