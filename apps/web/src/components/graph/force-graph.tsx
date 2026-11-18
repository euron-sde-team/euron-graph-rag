"use client";

import { Maximize2, Minus, Plus } from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";

import { Button } from "@/components/ui/button";
import {
  boundsOf,
  communityColor,
  computeLayout,
  fitTransform,
  neighbourhood,
  nodeRadius,
  predicateLabel,
  typeColor,
  typeLabel,
  type Point,
} from "@/lib/graph";

export type GraphNode = {
  id: string;
  name: string;
  type: string;
  importance: number;
  degree: number;
  communityOrdinal?: number | null;
  /** Drawn emphasised: the seeds of a question, say. */
  emphasis?: boolean;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  predicate: string;
  weight: number;
};

type Transform = { k: number; x: number; y: number };
type UserView = { layout: Map<string, Point>; view: Transform; dragged: Map<string, Point> };

const NO_DRAG: Map<string, Point> = new Map();

const WIDTH = 960;
const HEIGHT = 600;
const MIN_ZOOM = 0.25;
const MAX_ZOOM = 4;

/**
 * An interactive force-directed graph in SVG. The layout is computed once per graph
 * (lib/graph.ts), so it appears settled; nodes can then be dragged, the view panned and
 * zoomed, and every node is a focusable button for keyboard users. Labels follow importance:
 * the larger half is always named, the rest appear on hover, selection or zoom.
 */
export function ForceGraph({
  nodes,
  edges,
  colorBy,
  selectedId,
  onSelect,
  onOpen,
  height = HEIGHT,
  label = "Knowledge graph",
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  colorBy: "type" | "community";
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  /** Double click or Enter on a selected node: dive into its neighbourhood. */
  onOpen?: (id: string) => void;
  height?: number;
  label?: string;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  // The layout is a pure function of the graph, so it is computed once per graph and the
  // view (pan, zoom, dragged nodes) is remembered only for that same layout: a new graph
  // starts framed to fit without any effect resetting state.
  const layout = useMemo(
    () => computeLayout(nodes, edges, { width: WIDTH, height }),
    [nodes, edges, height],
  );
  const fitView = useMemo(
    () => fitTransform(boundsOf(layout.values(), 28), WIDTH, height),
    [layout, height],
  );
  const [user, setUser] = useState<UserView | null>(null);
  const current = user?.layout === layout ? user : null;
  const view = current?.view ?? fitView;
  const dragged = current?.dragged ?? NO_DRAG;

  const change = useCallback(
    (
      patch: (
        base: Pick<UserView, "view" | "dragged">,
      ) => Partial<Pick<UserView, "view" | "dragged">>,
    ) =>
      setUser((old) => {
        const base = old?.layout === layout ? old : { layout, view: fitView, dragged: NO_DRAG };
        return { ...base, ...patch(base) };
      }),
    [layout, fitView],
  );
  const setView = useCallback(
    (next: Transform | ((v: Transform) => Transform)) =>
      change((base) => ({ view: typeof next === "function" ? next(base.view) : next })),
    [change],
  );
  const fit = () => setUser({ layout, view: fitView, dragged: NO_DRAG });

  const position = (id: string): Point =>
    dragged.get(id) ?? layout.get(id) ?? { x: WIDTH / 2, y: height / 2 };

  const maxImportance = useMemo(() => Math.max(0, ...nodes.map((n) => n.importance)), [nodes]);
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const focus = hovered ?? selectedId;
  const near = useMemo(() => neighbourhood(focus, edges), [focus, edges]);
  const labelled = useMemo(() => {
    const ranked = [...nodes].sort((a, b) => b.importance - a.importance);
    return new Set(ranked.slice(0, Math.max(8, Math.ceil(nodes.length * 0.5))).map((n) => n.id));
  }, [nodes]);

  // Wheel zoom around the pointer. React registers wheel listeners as passive, which cannot
  // stop the page from scrolling, so the listener is attached by hand.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const element = svg;
    function onWheel(event: WheelEvent) {
      event.preventDefault();
      const rect = element.getBoundingClientRect();
      const px = ((event.clientX - rect.left) / rect.width) * WIDTH;
      const py = ((event.clientY - rect.top) / rect.height) * height;
      setView((v) => {
        const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, v.k * Math.exp(-event.deltaY * 0.0015)));
        return { k, x: px - ((px - v.x) / v.k) * k, y: py - ((py - v.y) / v.k) * k };
      });
    }
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  }, [height, setView]);

  const drag = useRef<
    | { kind: "pan"; startX: number; startY: number; origin: Transform }
    | { kind: "node"; id: string; moved: boolean }
    | null
  >(null);

  function toSvg(event: { clientX: number; clientY: number }): Point {
    const rect = svgRef.current!.getBoundingClientRect();
    return {
      x: ((event.clientX - rect.left) / rect.width) * WIDTH,
      y: ((event.clientY - rect.top) / rect.height) * height,
    };
  }

  function onBackgroundDown(event: ReactPointerEvent<SVGRectElement>) {
    (event.target as Element).setPointerCapture(event.pointerId);
    const p = toSvg(event);
    drag.current = { kind: "pan", startX: p.x, startY: p.y, origin: view };
  }

  function onNodeDown(event: ReactPointerEvent<SVGGElement>, id: string) {
    event.stopPropagation();
    (event.currentTarget as Element).setPointerCapture(event.pointerId);
    drag.current = { kind: "node", id, moved: false };
  }

  function onMove(event: ReactPointerEvent<SVGSVGElement>) {
    const current = drag.current;
    if (!current) return;
    const p = toSvg(event);
    if (current.kind === "pan") {
      setView({
        k: current.origin.k,
        x: current.origin.x + (p.x - current.startX),
        y: current.origin.y + (p.y - current.startY),
      });
    } else {
      current.moved = true;
      change((base) => ({
        dragged: new Map(base.dragged).set(current.id, {
          x: (p.x - base.view.x) / base.view.k,
          y: (p.y - base.view.y) / base.view.k,
        }),
      }));
    }
  }

  function onUp(id?: string) {
    const current = drag.current;
    drag.current = null;
    if (current?.kind === "node" && !current.moved && id) onSelect(id === selectedId ? null : id);
  }

  function onKey(event: KeyboardEvent<SVGGElement>, id: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (id === selectedId && onOpen) onOpen(id);
      else onSelect(id);
    }
    if (event.key === "Escape") onSelect(null);
  }

  const zoomBy = (factor: number) =>
    setView((v) => {
      const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, v.k * factor));
      const cx = WIDTH / 2;
      const cy = height / 2;
      return { k, x: cx - ((cx - v.x) / v.k) * k, y: cy - ((cy - v.y) / v.k) * k };
    });

  const color = (n: GraphNode) =>
    colorBy === "community" ? communityColor(n.communityOrdinal) : typeColor(n.type);

  return (
    <div className="bg-card border-border relative overflow-hidden rounded-xl border">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${height}`}
        role="group"
        aria-label={`${label}: ${nodes.length} entities and ${edges.length} relations. Tab to a node and press Enter to select it.`}
        className="block h-auto w-full touch-none select-none"
        style={{ aspectRatio: `${WIDTH} / ${height}` }}
        onPointerMove={onMove}
        onPointerUp={() => onUp()}
      >
        <defs>
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M0 0 L10 5 L0 10 z" fill="var(--subtle)" />
          </marker>
        </defs>
        <rect
          width={WIDTH}
          height={height}
          fill="transparent"
          className="cursor-grab active:cursor-grabbing"
          onPointerDown={onBackgroundDown}
          onClick={() => onSelect(null)}
        />
        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          <g aria-hidden>
            {edges.map((edge) => {
              const a = position(edge.source);
              const b = position(edge.target);
              const lit = focus !== null && (edge.source === focus || edge.target === focus);
              const dim = focus !== null && !lit;
              const target = byId.get(edge.target);
              const gap = target ? nodeRadius(target.importance, maxImportance) + 2 : 0;
              const length = Math.hypot(b.x - a.x, b.y - a.y) || 1;
              return (
                <g key={edge.id}>
                  <line
                    x1={a.x}
                    y1={a.y}
                    x2={b.x - ((b.x - a.x) / length) * gap}
                    y2={b.y - ((b.y - a.y) / length) * gap}
                    stroke={lit ? "var(--primary)" : "var(--subtle)"}
                    strokeOpacity={
                      dim ? 0.08 : lit ? 0.95 : 0.3 + Math.min(0.3, edge.weight * 0.08)
                    }
                    strokeWidth={(lit ? 1.6 : 1) + Math.min(1.2, edge.weight * 0.25)}
                    markerEnd={lit ? "url(#arrow)" : undefined}
                  />
                  {lit && view.k > 0.7 ? (
                    <text
                      x={(a.x + b.x) / 2}
                      y={(a.y + b.y) / 2 - 3}
                      textAnchor="middle"
                      className="fill-muted-foreground text-[9px]"
                      paintOrder="stroke"
                      stroke="var(--card)"
                      strokeWidth={3}
                    >
                      {predicateLabel(edge.predicate)}
                    </text>
                  ) : null}
                </g>
              );
            })}
          </g>
          {nodes.map((node) => {
            const { x, y } = position(node.id);
            const r = nodeRadius(node.importance, maxImportance);
            const isFocus = node.id === focus;
            const inNear = focus === null || near.has(node.id);
            const selected = node.id === selectedId;
            const showLabel =
              selected || (inNear && focus !== null) || labelled.has(node.id) || view.k > 1.7;
            return (
              <g
                key={node.id}
                transform={`translate(${x} ${y})`}
                role="button"
                tabIndex={0}
                aria-label={`${node.name}, ${typeLabel(node.type)}, ${node.degree} connections`}
                aria-pressed={selected}
                opacity={inNear ? 1 : 0.18}
                className="cursor-pointer outline-none [&:focus-visible>circle:first-child]:stroke-[var(--ring)] [&:focus-visible>circle:first-child]:stroke-[3px]"
                onPointerDown={(e) => onNodeDown(e, node.id)}
                onPointerUp={() => onUp(node.id)}
                onPointerEnter={() => setHovered(node.id)}
                onPointerLeave={() => setHovered(null)}
                onDoubleClick={() => onOpen?.(node.id)}
                onKeyDown={(e) => onKey(e, node.id)}
                onFocus={() => setHovered(node.id)}
                onBlur={() => setHovered(null)}
              >
                {node.emphasis ? (
                  <circle
                    r={r + 5}
                    fill="none"
                    stroke={color(node)}
                    strokeOpacity={0.45}
                    strokeWidth={2}
                  />
                ) : null}
                <circle
                  r={r}
                  fill={color(node)}
                  fillOpacity={0.92}
                  stroke={selected || isFocus ? "var(--foreground)" : "var(--card)"}
                  strokeWidth={selected ? 2.5 : 1.5}
                />
                {showLabel ? (
                  <text
                    y={r + 11}
                    textAnchor="middle"
                    className="fill-foreground pointer-events-none text-[10.5px] font-medium"
                    paintOrder="stroke"
                    stroke="var(--card)"
                    strokeWidth={3.5}
                    strokeLinejoin="round"
                  >
                    {node.name}
                  </text>
                ) : null}
              </g>
            );
          })}
        </g>
      </svg>
      <div className="absolute top-3 right-3 flex flex-col gap-1.5">
        <Button variant="secondary" size="icon-sm" aria-label="Zoom in" onClick={() => zoomBy(1.3)}>
          <Plus />
        </Button>
        <Button
          variant="secondary"
          size="icon-sm"
          aria-label="Zoom out"
          onClick={() => zoomBy(1 / 1.3)}
        >
          <Minus />
        </Button>
        <Button variant="secondary" size="icon-sm" aria-label="Fit to view" onClick={fit}>
          <Maximize2 />
        </Button>
      </div>
    </div>
  );
}
