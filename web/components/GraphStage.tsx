"use client";

import { memo, useEffect, useRef, useState, type CSSProperties } from "react";
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
import { SPRING } from "@/lib/motion";
import { useEvidenceSheet } from "./EvidenceSheet";
import { cn } from "@/lib/cn";
import { useNexus } from "@/lib/useNexus";
import {
  equalGoals,
  equalSteps,
  equalHistoryLite,
  selectGraphGoal as selectGoal,
  selectGraphHistory as selectHistoryLite,
  selectGraphPlan as selectPlanLite,
  type HistoryLite,
  type PlanLite,
} from "@/lib/graphData";
import { Network } from "lucide-react";

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

/** Stage-scale layout: the graph fills the whole center column, so link
 * distances and repulsion are tuned larger than a side-panel plot. */
const LINK_STEP = 150;
const LINK_EVIDENCE = 82;

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

function buildModel(goal: string, history: HistoryLite[], plan: PlanLite[]): {
  nodes: SimpleNode[];
  links: SimpleLink[];
} {
  const nodes: SimpleNode[] = [{ id: "goal", type: "goal", verdict: "active", label: goal, r: 14 }];
  const links: SimpleLink[] = [];
  const seen = new Set<string>(["goal"]);

  const addNode = (node: SimpleNode): boolean => {
    if (nodes.length >= MAX_NODES) return false;
    if (seen.has(node.id)) return true;
    seen.add(node.id);
    nodes.push(node);
    return true;
  };

  history.forEach((record, i) => {
    const id = `h-${i}`;
    if (!addNode({ id, type: "step", verdict: record.complete ? "done" : record.verdict, label: record.instruction, r: 9 })) return;
    links.push({ source: "goal", target: id, dist: LINK_STEP });
    for (const evidence of record.evidences) {
      if (nodes.length >= MAX_NODES) break;
      if (addNode({ id: evidence.id, type: "evidence", verdict: record.complete ? "done" : "retry", label: evidence.summarized, r: 5, evidenceId: evidence.id })) {
        links.push({ source: id, target: evidence.id, dist: LINK_EVIDENCE });
      }
    }
  });

  plan.forEach((step, i) => {
    const id = `p-${i}`;
    if (!addNode({ id, type: "step", verdict: i === 0 ? "active" : "queued", label: step.instruction, r: 9 })) return;
    links.push({ source: "goal", target: id, dist: LINK_STEP });
  });

  return { nodes, links };
}

/** Full-stage (center column) knowledge graph: goal anchors the middle,
 * steps orbit it, evidence blooms off its step. Clicking an evidence dot
 * opens the sheet. */
function GraphStageBase({ className }: { className?: string }) {
  const goal = useNexus(selectGoal, equalGoals);
  const history = useNexus(selectHistoryLite, equalHistoryLite);
  const plan = useNexus(selectPlanLite, equalSteps);
  const { open } = useEvidenceSheet();

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const nodesRef = useRef<Map<string, GNode>>(new Map());
  const linksRef = useRef<GLink[]>([]);
  const simRef = useRef<Simulation<GNode, GLink> | null>(null);
  const dataRef = useRef({ goal, history, plan });
  const [, setTick] = useState(0);
  const [hover, setHover] = useState<{ node: GNode; x: number; y: number } | null>(null);

  const sig = `${history.length}:${plan.length}:${goal.length}`;

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
    const model = buildModel(dataRef.current.goal, dataRef.current.history, dataRef.current.plan);
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

    const linkForce = forceLink<GNode, GLink>(links).id((d) => d.id).distance((l) => l.dist).strength(0.6);

    if (!simRef.current) {
      const sim = forceSimulation<GNode, GLink>(merged)
        .force("charge", forceManyBody<GNode>().strength((d) => (d.type === "goal" ? -320 : -150)))
        .force("collide", forceCollide<GNode>((d) => d.r + 6).iterations(1.4))
        .force("x", forceX<GNode>(0).strength(0.04))
        .force("y", forceY<GNode>(0).strength(0.035))
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

  useEffect(
    () => () => {
      simRef.current?.stop();
      simRef.current = null;
      nodesRef.current = new Map();
    },
    []
  );

  const nodes = [...nodesRef.current.values()];
  const { w, h } = size;

  return (
    <div className={cn("relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden p-2.5", className)}>
      <div className="fill relative flex min-h-0 w-full flex-1 flex-col overflow-hidden">
        <div className="pointer-events-none absolute left-3 top-3 z-10 flex items-center gap-2">
          <span className="live-dot" data-paused="false">
            <Network size={11} className="shrink-0" />
            GRAPH
            <span className="num font-normal opacity-80">{nodes.length} nodes</span>
          </span>
        </div>

        <div ref={containerRef} className="relative min-h-0 min-w-0 flex-1" onMouseLeave={() => setHover(null)}>
          <svg width={w} height={h} className="block h-full w-full" role="img" aria-label="Force-directed graph of goal, steps and evidence">
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
                  <line key={`l${i}`} x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke="rgb(148 163 184 / .2)" strokeWidth={1.4} />
                );
              })}
              {nodes.map((node) => (
                <GraphNode
                  key={node.id}
                  node={node}
                  onEnter={() => node.x !== undefined && setHover({ node, x: node.x, y: node.y ?? 0 })}
                  onLeave={() => setHover((cur) => (cur?.node.id === node.id ? null : cur))}
                  onOpen={node.evidenceId ? () => open(node.evidenceId as string) : undefined}
                />
              ))}
            </g>
          </svg>
          <AnimatePresence>{hover && <NodeTooltip node={hover.node} left={hover.x + w / 2} top={hover.y + h / 2} />}</AnimatePresence>
          {nodes.length <= 1 && (
            <div className="absolute inset-0 grid place-items-center">
              <p className="max-w-[300px] px-4 text-center text-[13px] leading-snug text-(--dim)">
                Once the plan starts, the goal anchors the center; steps orbit it, and verified evidence blooms off its step.
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="caption mt-2 flex shrink-0 flex-wrap items-center gap-3 px-1">
        <Legend color={VERDICT_COLOR.active} label="goal / active" shape="solid" />
        <Legend color={VERDICT_COLOR.done} label="done" shape="ring" />
        <Legend color={VERDICT_COLOR.retry} label="retry" shape="ring" />
        <Legend color={VERDICT_COLOR.replan} label="replan" shape="ring" />
        <Legend color={VERDICT_COLOR.queued} label="queued" shape="ring" />
        <span className="faint ml-auto normal-case tracking-normal">click evidence to open · capped at 120 nodes</span>
      </div>
    </div>
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
        animate={{ scale: 1, opacity: node.type === "evidence" ? 0.95 : 1 }}
        style={{ transformBox: "fill-box", transformOrigin: "center" } as CSSProperties}
        transition={spring}
        r={node.r}
        fill={node.type === "goal" ? "url(#kg-goal)" : node.verdict === "queued" ? "transparent" : VERDICT_COLOR[node.verdict]}
        stroke={node.type === "goal" ? undefined : VERDICT_COLOR[node.verdict]}
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
        {node.type === "goal" ? "goal" : node.type === "evidence" ? `evidence ${node.evidenceId}` : `step · ${node.verdict}`}
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

export const GraphStage = memo(GraphStageBase);
