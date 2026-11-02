"use client";

import { useCallback, useEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Sparkle, Square } from "lucide-react";

import { cn } from "@/lib/cn";
import { stringsEqual } from "@/lib/equal";
import { SPRING } from "@/lib/motion";
import { selectPhase } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { store } from "@/lib/store";
import { cancelRun, RunApiError, startRun } from "@/lib/api";
import { Magnetic } from "./ui";

const MAX_GOAL = 2000;

/** Neutral, science/tech-only prompts the composer can autofill. */
const EXAMPLES = [
  "Find the launch date and cost of the James Webb Space Telescope and summarize both.",
  "Look up the Python 3.13 release notes on python.org and list three new features.",
  "Open the README of the React GitHub repo and summarize how to install it.",
];

interface Props {
  /** Docked bar variant once a run exists; the hero variant shows example chips. */
  docked?: boolean;
  className?: string;
}

export function MissionComposer({ docked = false, className }: Props) {
  const phase = useNexus(selectPhase);
  const status = useNexus((s) => s.data?.status ?? "", stringsEqual);
  const busy = status === "running" || status === "reporting";

  const [value, setValue] = useState("");
  const [sending, setSending] = useState(false);
  const areaRef = useRef<HTMLTextAreaElement>(null);

  const trimmed = value.trim();
  const tooLong = value.length > MAX_GOAL;
  const blocked = busy || sending;

  /** Auto-grow the textarea up to the variant's cap. */
  const autoGrow = useCallback(() => {
    const area = areaRef.current;
    if (!area) return;
    area.style.height = "0px";
    area.style.height = `${Math.min(area.scrollHeight, docked ? 88 : 170)}px`;
  }, [docked]);
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

  const cancel = useCallback((): void => {
    cancelRun().catch((error: unknown) => {
      if (error instanceof RunApiError && error.kind === "network") {
        store.pushToast({ kind: "notice", title: "Agent unreachable", detail: error.message });
      }
    });
  }, []);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>): void => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className={cn(docked && "pointer-events-none fixed inset-x-0 bottom-4 z-40 flex justify-center px-4")}>
      <div
        className={cn(
          "composer glass relative flex flex-col",
          docked ? "pointer-events-auto w-full gap-1.5 rounded-[22px] p-2.5 md:max-w-[54rem]" : "rounded-[26px] p-4",
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
          placeholder={docked ? "Queue another goal…" : "Describe a goal for the agent…  Ctrl/⌘+Enter to start"}
          aria-label={docked ? "Queue another goal" : "Mission goal"}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <span className={cn("counter absolute right-0 bottom-0.5", tooLong && "counter-over")}>
          {value.length}/{MAX_GOAL}
        </span>
      </div>

      {!docked && (
        <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
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
      )}

      <div className="flex items-center justify-end gap-2">
        <span className="caption shrink-0 pr-1">
          {blocked ? (busy ? "Agent working…" : "Starting…") : phase === "demo" ? "demo — Start restarts the replay" : ""}
        </span>
        <AnimatePresence>
          {busy && (
            <motion.button
              type="button"
              initial={{ opacity: 0, scale: 0.85, width: 0 }}
              animate={{ opacity: 1, scale: 1, width: "auto" }}
              exit={{ opacity: 0, scale: 0.85, width: 0 }}
              transition={SPRING}
              onClick={cancel}
              className="pill shrink-0 justify-center"
              style={{ "--tone": "var(--warn)" } as CSSProperties}
              title="Cancel the running agent"
            >
              <Square size={11} />
              Cancel
            </motion.button>
          )}
        </AnimatePresence>
        <Magnetic>
          <motion.button
            type="button"
            whileTap={{ scale: 0.96 }}
            transition={SPRING}
            disabled={blocked || !trimmed || tooLong}
            onClick={submit}
            className={cn("composer-start", docked ? "px-4 py-2" : "")}
            title="Start the run"
          >
            <Sparkle size={13} />
            {busy ? "Agent working…" : sending ? "Starting…" : "Start"}
          </motion.button>
        </Magnetic>
      </div>
      </div>
    </div>
  );
}
