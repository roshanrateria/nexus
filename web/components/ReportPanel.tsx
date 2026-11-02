"use client";

import { memo, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText } from "lucide-react";
import { reportEqual, selectReport } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { cn } from "@/lib/cn";
import { CopyButton, Panel } from "./ui";
import { EvidenceChip } from "./EvidenceSheet";

/** Wrap report citations like [E3], [7], [3, 7] into evidence:// links; code
 * fences are left untouched. */
export function linkifyReport(text: string): string {
  const parts = text.split(/```/);
  return parts
    .map((part, i) => {
      if (i % 2 === 1) return part;
      return part.replace(/\[(E?\s?\d+(?:\s*,\s*\d+)*)\]/g, (m, inner: string) => {
        const nums = inner.replace(/\s+/g, "").replace(/^E/, "").split(",").filter(Boolean);
        if (nums.length === 0 || nums.length > 4) return m;
        return nums.map((n) => `[E${n}](evidence://E${n})`).join(" ");
      });
    })
    .join("```");
}

function basename(path: string): string {
  const i = path.lastIndexOf("/");
  return i >= 0 ? path.slice(i + 1) : path;
}

function ReportMarkdown({ text }: { text: string }) {
  const linked = useMemo(() => linkifyReport(text), [text]);
  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            if (href && href.startsWith("evidence://")) {
              const id = href.slice("evidence://".length);
              return <EvidenceChip id={id} />;
            }
            const external = Boolean(href && /^https?:\/\//.test(href));
            return (
              <a
                href={external ? href : undefined}
                target={external ? "_blank" : undefined}
                rel={external ? "noopener noreferrer" : undefined}
              >
                {children}
              </a>
            );
          },
        }}
      >
        {linked}
      </ReactMarkdown>
    </div>
  );
}

function ReportPanelBase({ className }: { className?: string }) {
  const { report, reportPath, status } = useNexus(selectReport, reportEqual);
  const reporting = status === "reporting";

  return (
    <Panel
      title="Report"
      right={
        <div className="flex items-center gap-2">
          {reportPath && <span className="chip font-mono max-w-[180px] truncate">{basename(reportPath)}</span>}
          {report && <CopyButton text={report} label="Copy the report" />}
        </div>
      }
      className={cn("lg:col-span-8", className)}
      enterIndex={7}
    >
      {report ? (
        <div className={cn("scroll min-h-0 flex-1 overflow-y-auto pr-2", reporting && "caret")}>
          <ReportMarkdown text={report} />
        </div>
      ) : (
        <div className="fill flex h-full min-h-[140px] flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
          <FileText size={20} className="text-(--faint)" />
          <p className="text-[13px] text-(--dim)">The final report will stream here once the agent finishes.</p>
          <p className="text-[11.5px] text-(--faint)">
            Written only from verified evidence, with inline <span className="font-mono">[E#]</span> citations.
          </p>
        </div>
      )}
    </Panel>
  );
}

export const ReportPanel = memo(ReportPanelBase);
