"use client";

import { useEffect, useRef, memo, useState, type CSSProperties } from "react";
import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { AnimatePresence, motion } from "framer-motion";
import { selectEvidences, selectTimeline } from "@/lib/selectors";
import { useNexus } from "@/lib/useNexus";
import { SPRING } from "@/lib/motion";
import { useEvidenceSheet } from "./EvidenceSheet";
import { cn } from "@/lib/cn";
import { Panel } from "./ui";

interface GNode extends SimulationNodeDatum {
  id: string;
  type: "goal" | "step" | "evidence";
  verdict: "done" | "retry" | "replan" | "active" | "queued";
  label: string;
  r: number;
  evidenceId?: string;
}

interface GLink extends SimulationLinkDatum<GNode> {
  dist: number;
}

const MAX_NODES = 120;

const VERDICT_COLOR: Record<GNode["verdict"], string> = {
  done: "var(--ok)",
  retry: "var(--warn)",
  replan: "var(--bad)",
  active: "var(--violet)",
  queued: "var(--run)",
};

interface SimpleNode {
  id: string;
  type: GNode["type"];
  verdict: GNode["verdict"];
  label: string;
  r: number;
  evidenceId?: string;
}

interface SimpleLink {
  source: string;
  target: string;
  dist: number;
}

function buildModel(goal: string, history: HistoryRecordLite[], plan: PlanStepLite[]): {
  nodes: SimpleNode[];
  links: SimpleLink[];
} {
  const nodes: SimpleNode[] = [
    { id: "goal", type: "goal", verdict: "active", label: goal, r: 11 },
  ];
  const links: SimpleLink[] = [];
  const seen = new Set<string>(["goal"]);

  const addNode = (node: SimpleNode): boolean => {
    if (nodes.length >= MAX_NODES || seen.has(node.id)) return nodes.length < MAX_NODES && seen.has(node.id);
    seen.add(node.id);
    nodes.push(node);
    return true;
  };

  history.forEach((record, i) => {
    const id = `h-${i}`;
    if (!addNode({ id, type: "step", verdict: record.complete ? "done" : record.verdict, label: record.instruction, r: 7 })) return;
    links.push({ source: "goal", target: id, dist: 78 });
    for (const evidence of record.evidences) {
      if (nodes.length >= MAX_NODES) break;
      if (addNode({ id: evidence.id, type: "evidence", verdict: record.complete ? "done" : "retry", label: evidence.summarized, r: 4, evidenceId: evidence.id })) {
        links.push({ source: id, target: evidence.id, dist: 44 });
      }
    }
  });

  plan.forEach((step, i) => {
    const id = `p-${i}`;
    if (!addNode({ id, type: "step", verdict: i === 0 ? "active" : "queued", label: step.instruction, r: 7 })) return;
    links.push({ source: "goal", target: id, dist: 78 });
  });

  return { nodes, links };
}

interface HistoryRecordLite {
  instruction: string;
  complete: boolean;
  verdict: "done" | "retry" | "replan";
  evidences: { id: string; summarized: string }[];
}

interface PlanStepLite {
  instruction: string;
}

function KnowledgeGraphBase({ className }: { className?: string }) {
  const goal = useNexus(selectGoal);
  const history = useNexus(selectHistoryLite, timelineHistoryEqual);
  const plan = useNexus(selectPlanLite, stepsOnlyEqual);
  const evidences = useNexus(selectEvidenceIds, evidenceCountEqual);
  const { open } = useEvidenceSheet();

  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const nodesRef = useRef<Map<string, GNode>>(new Map());
  const linksRef = useRef<GLink[]>([]);
  const simRef = useRef<Simulation<GNode, GLink> | null>(null);
  const dataRef = useRef({ goal, history, plan });
  const [, setTick] = useState(0);
  const [hover, setHover] = useState<{ node: GNode; x: number; y: number } | null>(null);

  const sig = `${history.length}:${plan.length}:${evidences.length}:${goal.length}`;

  // Keep the freshest raw slices; the simulation effect only fires on sig.
  useEffect(() => {
    dataRef.current = { goal, history, plan };
  });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = (): void => setSize({ w: el.clientWidth, h: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const model = buildModel(
      dataRef.current.goal,
      dataRef.current.history,
      dataRef.current.plan
    );
    const keep = nodesRef.current;
    const merged: GNode[] = [];
    const present = new Set<string>();
    for (const spec of model.nodes) {
      present.add(spec.id);
      const existing = keep.get(spec.id);
      if (existing) {
        existing.verdict = spec.verdict;
        existing.label = spec.label;
        merged.push(existing);
      } else {
        const node: GNode = {
          id: spec.id,
          type: spec.type,
          verdict: spec.verdict,
          label: spec.label,
          r: spec.r,
          evidenceId: spec.evidenceId,
        };
        keep.set(spec.id, node);
        merged.push(node);
      }
    }
    for (const id of [...keep.keys()]) {
      if (!present.has(id)) keep.delete(id);
    }

    const links: GLink[] = model.links.map((l) => ({ source: l.source, target: l.target, dist: l.dist }));
    linksRef.current = links;

    const linkForce = forceLink<GNode, GLink>(links)
      .id((d) => d.id)
      .distance((l) => l.dist)
      .strength(0.6);

    if (!simRef.current) {
      const sim = forceSimulation<GNode, GLink>(merged)
        .force("charge", forceManyBody<GNode>().strength((d) => (d.type === "goal" ? -170 : -92)))
        .force("collide", forceCollide<GNode>((d) => d.r + 3).iterations(1.4))
        .force("x", forceX<GNode>(0).strength(0.055))
        .force("y", forceY<GNode>(0).strength(0.05))
        .force("link", linkForce)
        .alphaMin(0.02)
        .on("tick", () => setTick((t) => t + 1));
      simRef.current = sim;
    } else {
      simRef.current.nodes(merged);
      simRef.current.force("link", linkForce);
      simRef.current.alpha(0.85);
      simRef.current.restart();
    }
  }, [sig]);

  useEffect(() => {
    return () => {
      simRef.current?.stop();
      simRef.current = null;
      nodesRef.current = new Map();
    };
  }, []);

  const nodes = [...nodesRef.current.values()];
  const { w, h } = size;

  return (
    <Panel
      title="Knowledge graph"
      right={<span className="chip num">{nodes.length} nodes</span>}
      className={cn("lg:col-span-4", className)}
      enterIndex={6}
      bodyClassName="flex flex-col"
    >
      <div ref={containerRef} className="relative min-h-[240px] flex-1" onMouseLeave={() => setHover(null)}>
        <svg
          width={w}
          height={h}
          className="block h-full w-full"
          role="img"
          aria-label="Force-directed graph of goal, steps and evidence"
        >
          <defs>
            <radialGradient id="kg-goal" cx="0.3" cy="0.25">
              <stop offset="0" stopColor="#a5b4fc" />
              <stop offset="1" stopColor="#6d28d9" />
            </radialGradient>
          </defs>
          <g transform={`translate(${w / 2},${h / 2})`}>
            {linksRef.current.map((link, i) => {
              const s = nodesRef.current.get(linkSourceId(link));
              const t = nodesRef.current.get(linkTargetId(link));
              if (!s || !t || s.x === undefined || t.x === undefined) return null;
              return (
                <line
                  key={`l${i}`}
                  x1={s.x}
                  y1={s.y}
                  x2={t.x}
                  y2={t.y}
                  stroke="rgb(148 163 184 / .2)"
                  strokeWidth={1}
                />
              );
            })}
            {nodes.map((node) => (
              <GraphNode
                key={node.id}
                node={node}
                onEnter={() => node.x !== undefined && setHover({ node, x: node.x, y: node.y ?? 0 })}
                onLeave={() => setHover((cur) => (cur?.node.id === node.id ? null : cur))}
                onOpen={
                  node.evidenceId
                    ? () => open(node.evidenceId as string)
                    : undefined
                }
              />
            ))}
          </g>
        </svg>
        <AnimatePresence>
          {hover && <NodeTooltip node={hover.node} left={hover.x + w / 2} top={hover.y + h / 2} />}
        </AnimatePresence>
        {nodes.length <= 1 && (
          <div className="absolute inset-0 grid place-items-center">
            <p className="max-w-[260px] text-center text-[13px] leading-snug text-(--dim)">
              The goal anchors the center; steps orbit it, and verified evidence blooms off its step.
            </p>
          </div>
        )}
      </div>
      <div className="caption mt-2 flex shrink-0 flex-wrap items-center gap-3">
        <Legend color={VERDICT_COLOR.active} label="goal / active" shape="solid" />
        <Legend color={VERDICT_COLOR.done} label="done" shape="ring" />
        <Legend color={VERDICT_COLOR.retry} label="retry" shape="ring" />
        <Legend color={VERDICT_COLOR.replan} label="replan" shape="ring" />
        <Legend color={VERDICT_COLOR.queued} label="queued" shape="ring" />
        <span className="ml-auto normal-case">click evidence · capped at 120 nodes</span>
      </div>
    </Panel>
  );
}

function linkSourceId(link: GLink): string {
  return typeof link.source === "object" ? link.source.id : String(link.source);
}

function linkTargetId(link: GLink): string {
  return typeof link.target === "object" ? link.target.id : String(link.target);
}

function GraphNode({
  node,
  onEnter,
  onLeave,
  onOpen,
}: {
  node: GNode;
  onEnter: () => void;
  onLeave: () => void;
  onOpen?: () => void;
}) {
  const interactive = node.evidenceId !== undefined;
  const spring = { type: "spring" as const, stiffness: 300, damping: 30 };
  return (
    <g
      transform={`translate(${node.x ?? 0},${node.y ?? 0})`}
      className={cn(interactive && "cursor-pointer")}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onFocus={interactive ? onEnter : undefined}
      onBlur={interactive ? onLeave : undefined}
      onClick={onOpen}
      onKeyDown={
        interactive
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onOpen?.();
              }
            }
          : undefined
      }
      tabIndex={interactive ? 0 : undefined}
      role={interactive ? "button" : undefined}
      aria-label={interactive ? `Open evidence ${node.evidenceId}` : undefined}
    >
      <motion.circle
        initial={{ scale: 0, opacity: 0 }}
        animate={{
          scale: 1,
          opacity: node.type === "evidence" ? 0.95 : 1,
        }}
        style={{ transformBox: "fill-box", transformOrigin: "center" } as CSSProperties}
        transition={spring}
        r={node.r}
        fill={
          node.type === "goal"
            ? "url(#kg-goal)"
            : node.verdict === "queued"
              ? "transparent"
              : VERDICT_COLOR[node.verdict]
        }
        stroke={
          node.type === "goal"
            ? undefined
            : VERDICT_COLOR[node.verdict]
        }
        strokeWidth={node.type === "evidence" ? 1.1 : node.verdict === "queued" ? 1.6 : 1}
        strokeDasharray={node.verdict === "queued" ? "2 2.4" : undefined}
      />
      {node.type === "goal" && (
        <motion.circle
          r={node.r + 5}
          fill="none"
          stroke="var(--violet)"
          strokeOpacity={0.4}
          animate={{ scale: [1, 1.25, 1], opacity: [0.4, 0.1, 0.4] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
          style={{ transformBox: "fill-box", transformOrigin: "center" } as CSSProperties}
        />
      )}
    </g>
  );
}

function NodeTooltip({ node, left, top }: { node: GNode; left: number; top: number }) {
  const { open } = useEvidenceSheet();
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.88 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.92 }}
      transition={SPRING}
      className="pointer-events-none absolute z-20 w-[248px] -translate-x-1/2 -translate-y-[calc(100%+10px)] rounded-xl border border-(--line) bg-[rgb(8_12_22/.95)] p-2.5 text-left shadow-[0_12px_32px_-12px_rgb(0_0_0/.6)]"
      style={{ left, top }}
    >
      <div className="caption">
        {node.type === "goal"
          ? "goal"
          : node.type === "evidence"
            ? `evidence ${node.evidenceId}`
            : `step · ${node.verdict}`}
      </div>
      <p className="mt-1 line-clamp-3 text-[12px] leading-snug text-(--text)">{node.label}</p>
      {node.evidenceId && (
        <button
          type="button"
          onClick={() => open(node.evidenceId as string)}
          className="pointer-events-auto mt-2 text-[11px] font-medium text-(--violet) hover:underline"
        >
          open in sheet →
        </button>
      )}
    </motion.div>
  );
}

function Legend({ color, label, shape }: { color: string; label: string; shape: "solid" | "ring" }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className="h-2.5 w-2.5 rounded-full"
        style={{
          backgroundColor: shape === "solid" ? color : "transparent",
          border: `1.6px solid ${color}`,
        }}
      />
      {label}
    </span>
  );
}

export const KnowledgeGraph = memo(KnowledgeGraphBase);

function timelineHistoryEqual(
  a: HistoryRecordLite[] | undefined,
  b: HistoryRecordLite[] | undefined
): boolean {
  if (a === b) return true;
  if (!a || !b || a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (
      a[i].instruction !== b[i].instruction ||
      a[i].complete !== b[i].complete ||
      a[i].verdict !== b[i].verdict ||
      a[i].evidences.length !== b[i].evidences.length
    ) {
      return false;
    }
  }
  return true;
}

const selectGoal = (s: Parameters<typeof selectTimeline>[0]) => s.data?.goal ?? "";
type GraphState = Parameters<typeof selectTimeline>[0];

const selectHistoryLite = (s: GraphState) => selectTimeline(s).history as HistoryRecordLite[];
const selectPlanLite = (s: GraphState) => selectTimeline(s).plan as PlanStepLite[];
const selectEvidenceIds = (s: GraphState) => selectEvidences(s) as { id: string }[];

function stepsOnlyEqual(
  a: PlanStepLite[] | undefined,
  b: PlanStepLite[] | undefined
): boolean {
  if (a === b) return true;
  if (!a || !b || a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i].instruction !== b[i].instruction) return false;
  }
  return true;
}

function evidenceCountEqual(a: EvidenceCount, b: EvidenceCount): boolean {
  return a.length === b.length;
}

type EvidenceCount = { id: string }[];
