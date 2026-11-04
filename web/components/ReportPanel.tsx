"use client";

import { memo, useEffect, useMemo, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download, FileText } from "lucide-react";
import { reportEqual, selectReport } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { cn } from "@/lib/cn";
import { CopyButton, IconButton, PanelEmpty } from "./ui";
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

/** Reading-typography markdown with [E#] chips that open the evidence sheet. */
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

function downloadReport(report: string, reportPath: string): void {
  const name = basename(reportPath) || "nexus-report.md";
  const blob = new Blob([report], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function ReportPanelBase({ className }: { className?: string }) {
  const { report, reportPath, status } = useNexus(selectReport, reportEqual);
  const reporting = status === "reporting";

  // While streaming, keep the newest text on screen (users can still scroll
  // away — following only resumes on new chunks below the fold).
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const followRef = useRef(true);
  useEffect(() => {
    const body = bodyRef.current;
    if (!body) return;
    const onScroll = (): void => {
      followRef.current = body.scrollTop + body.clientHeight >= body.scrollHeight - 48;
    };
    body.addEventListener("scroll", onScroll, { passive: true });
    return () => body.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    const body = bodyRef.current;
    if (body && report && followRef.current) body.scrollTop = body.scrollHeight;
  }, [report]);

  return (
    <section className={cn("fill relative flex min-h-0 min-w-0 flex-1 flex-col p-4", className)}>
      <header className="mb-2 flex shrink-0 items-center justify-between gap-2 px-1">
        <div className="flex items-center gap-2">
          <h2 className="caption">Report</h2>
          {reporting && <span className="chip text-(--violet)">streaming…</span>}
        </div>
        {report && (
          <div className="flex shrink-0 items-center gap-1.5">
            {reportPath && <span className="chip font-mono max-w-[200px] truncate">{basename(reportPath)}</span>}
            <CopyButton text={report} label="Copy the report" />
            <IconButton label="Download the report as .md" title="Download the report as .md" onClick={() => downloadReport(report, reportPath)}>
              <Download size={15} />
            </IconButton>
          </div>
        )}
      </header>

      {report ? (
        <div
          ref={bodyRef}
          className={cn("md-read scroll mx-auto min-h-0 w-full flex-1 overflow-y-auto pr-2", reporting && "caret")}
          data-testid="report-body"
        >
          <ReportMarkdown text={report} />
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="fill flex h-full min-h-[160px] flex-1 flex-col justify-center">
            <PanelEmpty
              icon={<FileText size={22} />}
              title="The final report will stream here when the agent reaches the goal."
              hint="Written only from verified evidence, with inline [E#] citations."
            />
          </div>
        </div>
      )}
    </section>
  );
}

export const ReportPanel = memo(ReportPanelBase);
