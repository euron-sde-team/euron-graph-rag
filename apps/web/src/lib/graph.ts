import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";

/** Entity types, their colours and the vocabulary the graph uses on screen. */

export const ENTITY_TYPES = [
  "PERSON",
  "ORGANIZATION",
  "LOCATION",
  "PRODUCT",
  "TECHNOLOGY",
  "EVENT",
  "CONCEPT",
  "OTHER",
] as const;

const TYPE_LABELS: Record<string, string> = {
  PERSON: "Person",
  ORGANIZATION: "Organization",
  LOCATION: "Location",
  PRODUCT: "Product",
  TECHNOLOGY: "Technology",
  EVENT: "Event",
  CONCEPT: "Concept",
  OTHER: "Other",
};

export function typeLabel(type: string): string {
  return TYPE_LABELS[type] ?? type.charAt(0) + type.slice(1).toLowerCase().replace(/_/g, " ");
}

export function typeColor(type: string): string {
  const key = type.toLowerCase();
  return (ENTITY_TYPES as readonly string[]).includes(type)
    ? `var(--type-${key})`
    : "var(--type-other)";
}

export const COMMUNITY_COLORS = 10;

export function communityColor(ordinal: number | null | undefined): string {
  return ordinal === null || ordinal === undefined
    ? "var(--type-other)"
    : `var(--community-${ordinal % COMMUNITY_COLORS})`;
}

/** "PARTNERED_WITH" -> "partnered with". */
export function predicateLabel(predicate: string): string {
  return predicate.toLowerCase().replace(/_/g, " ");
}

export type LayoutNode = { id: string; importance: number; degree: number };
export type LayoutEdge = { source: string; target: string; weight: number };
export type Point = { x: number; y: number };

export function nodeRadius(importance: number, max: number): number {
  const scale = max > 0 ? Math.sqrt(Math.max(importance, 0) / max) : 0;
  return 5 + scale * 13;
}

type SimNode = SimulationNodeDatum & { id: string; radius: number };

/**
 * A settled force layout, computed synchronously so the first paint is already stable (no
 * visible "swimming", and screenshots are reproducible). d3-force starts from a fixed spiral
 * and uses a fixed random sequence, so the same graph always lays out the same way. Nodes in
 * `previous` keep their position as the starting point, so changing a filter does not
 * scramble what stays on screen.
 */
export function computeLayout(
  nodes: LayoutNode[],
  edges: LayoutEdge[],
  options: { width: number; height: number; previous?: Map<string, Point>; ticks?: number },
): Map<string, Point> {
  const { width, height, previous, ticks = 320 } = options;
  const max = Math.max(0, ...nodes.map((n) => n.importance));
  const sim: SimNode[] = nodes.map((n) => {
    const known = previous?.get(n.id);
    return {
      id: n.id,
      radius: nodeRadius(n.importance, max),
      ...(known ? { x: known.x, y: known.y } : {}),
    };
  });
  const ids = new Set(nodes.map((n) => n.id));
  const kept = edges.filter((e) => ids.has(e.source) && ids.has(e.target));
  const links: SimulationLinkDatum<SimNode>[] = kept.map((e) => ({
    source: e.source,
    target: e.target,
  }));
  const simulation = forceSimulation(sim)
    .force(
      "link",
      forceLink<SimNode, SimulationLinkDatum<SimNode>>(links)
        .id((d) => d.id)
        .distance((_, i) => 78 - Math.min(24, (kept[i]?.weight ?? 1) * 6))
        .strength(0.5),
    )
    .force("charge", forceManyBody<SimNode>().strength(-380).distanceMax(360))
    .force(
      "collide",
      forceCollide<SimNode>((d) => d.radius + 14),
    )
    // Weak pulls toward the middle keep disconnected clusters in view without crushing them.
    .force("x", forceX<SimNode>(width / 2).strength(0.16))
    .force("y", forceY<SimNode>(height / 2).strength(0.26))
    .stop();
  simulation.tick(ticks);
  return new Map(sim.map((n) => [n.id, { x: n.x ?? width / 2, y: n.y ?? height / 2 }]));
}

export type Bounds = { minX: number; minY: number; maxX: number; maxY: number };

/**
 * The box around `points`. With `trim` (a fraction), the outermost points on each side are
 * ignored, so a few stray nodes do not shrink the whole picture to fit them.
 */
export function boundsOf(points: Iterable<Point>, padding = 0, trim = 0): Bounds | null {
  const all = [...points];
  if (!all.length) return null;
  const cut = Math.floor(all.length * trim);
  const xs = all.map((p) => p.x).sort((a, b) => a - b);
  const ys = all.map((p) => p.y).sort((a, b) => a - b);
  return {
    minX: (xs[cut] ?? 0) - padding,
    maxX: (xs[xs.length - 1 - cut] ?? 0) + padding,
    minY: (ys[cut] ?? 0) - padding,
    maxY: (ys[ys.length - 1 - cut] ?? 0) + padding,
  };
}

/** The scale and offset that fit `bounds` inside a viewport, centred. */
export function fitTransform(
  bounds: Bounds | null,
  width: number,
  height: number,
  maxScale = 1.6,
): { k: number; x: number; y: number } {
  if (!bounds) return { k: 1, x: 0, y: 0 };
  const w = Math.max(1, bounds.maxX - bounds.minX);
  const h = Math.max(1, bounds.maxY - bounds.minY);
  const k = Math.min(maxScale, Math.min(width / w, height / h));
  return {
    k,
    x: (width - w * k) / 2 - bounds.minX * k,
    y: (height - h * k) / 2 - bounds.minY * k,
  };
}

/** Ids a selection touches: the node itself and everything one edge away. */
export function neighbourhood(selected: string | null, edges: LayoutEdge[]): Set<string> {
  const ids = new Set<string>();
  if (!selected) return ids;
  ids.add(selected);
  for (const edge of edges) {
    if (edge.source === selected) ids.add(edge.target);
    if (edge.target === selected) ids.add(edge.source);
  }
  return ids;
}
