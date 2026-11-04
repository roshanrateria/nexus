"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { motion } from "framer-motion";
import { Sparkle } from "lucide-react";

import { cn } from "@/lib/cn";
import { SPRING } from "@/lib/motion";
import { selectPhase, selectStatusString } from "@/lib/selectors";
import { stringsEqual } from "@/lib/equal";
import { useNexus } from "@/lib/useNexus";
import { store } from "@/lib/store";
import { startRun, RunApiError } from "@/lib/api";
import { Magnetic } from "./ui";

const MAX_GOAL = 2000;

/** Neutral, science/tech-only prompts the composer can autofill. */
const EXAMPLES = [
  "Find the launch date and cost of the James Webb Space Telescope and summarize both.",
  "Look up the Python 3.13 release notes on python.org and list three new features.",
  "Open the README of the React GitHub repo and summarize how to install it.",
];

interface Props {
  className?: string;
}

export function MissionComposer({ className }: Props) {
  const phase = useNexus(selectPhase);
  const status = useNexus(selectStatusString, stringsEqual);
  const busy = status === "running" || status === "reporting";

  const [value, setValue] = useState("");
  const [sending, setSending] = useState(false);
  const areaRef = useRef<HTMLTextAreaElement>(null);

  const trimmed = value.trim();
  const tooLong = value.length > MAX_GOAL;
  const blocked = busy || sending;

  /** Auto-grow the textarea up to the sheet cap. */
  const autoGrow = useCallback(() => {
    const area = areaRef.current;
    if (!area) return;
    area.style.height = "0px";
    area.style.height = `${Math.min(area.scrollHeight, 170)}px`;
  }, []);
  useEffect(autoGrow, [value, autoGrow]);

  const submit = useCallback((): void => {
    if (blocked || !trimmed || tooLong) return;
    setSending(true);
    const clear = () => setSending(false);
    if (phase === "demo") {
      store.startDemo(); // restart the scripted replay; no network calls
      setValue("");
      setSending(false);
      return;
    }
    startRun(trimmed)
      .then(() => setValue(""))
      .catch((error: unknown) => {
        if (error instanceof RunApiError) {
          const title =
            error.kind === "busy" ? "Agent is busy" : error.kind === "network" ? "Agent unreachable" : "Could not start the run";
          store.pushToast({ kind: "notice", title, detail: error.message }); // text stays put
        }
      })
      .finally(clear);
  }, [blocked, trimmed, tooLong, phase]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>): void => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div
      className={cn(
        "composer glass relative flex flex-col gap-1 p-2.5",
        className
      )}
    >
      <div className="relative min-w-0">
        <textarea
          ref={areaRef}
          className="composer-field block"
          rows={1}
          value={value}
          disabled={blocked}
          placeholder="Describe a goal for the agent…  Ctrl/⌘+Enter to start"
          aria-label="Mission goal"
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
        />
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            disabled={blocked}
            className="chip max-w-full cursor-pointer transition-colors hover:border-(--violet)/40 hover:text-(--text) disabled:cursor-not-allowed disabled:opacity-60"
            title="Use this example goal"
            onClick={() => {
              setValue(example);
              areaRef.current?.focus();
            }}
          >
            <span className="truncate">{example}</span>
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between gap-2 pt-1">
        <span className="caption shrink-0">
          {blocked ? (busy ? "Agent working…" : "Starting…") : phase === "demo" ? "demo — Start restarts the replay" : ""}
        </span>
        <Magnetic>
          <motion.button
            type="button"
            whileTap={{ scale: 0.96 }}
            transition={SPRING}
            disabled={blocked || !trimmed || tooLong}
            onClick={submit}
            className="composer-start"
            title="Start the run"
          >
            <Sparkle size={13} />
            {busy ? "Agent working…" : sending ? "Starting…" : "Start"}
          </motion.button>
        </Magnetic>
      </div>
    </div>
  );
}
