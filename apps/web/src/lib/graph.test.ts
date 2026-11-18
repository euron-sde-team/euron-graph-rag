import { describe, expect, it } from "vitest";

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
} from "./graph";

const nodes = Array.from({ length: 12 }, (_, i) => ({
  id: `n${i}`,
  importance: 12 - i,
  degree: 3,
}));
const edges = nodes.slice(1).map((n, i) => ({ source: "n0", target: n.id, weight: 1 + (i % 3) }));

describe("labels and colours", () => {
  it("name types and fall back for unknown ones", () => {
    expect(typeLabel("ORGANIZATION")).toBe("Organization");
    expect(typeLabel("SPACE_STATION")).toBe("Space station");
    expect(typeColor("PERSON")).toBe("var(--type-person)");
    expect(typeColor("SPACE_STATION")).toBe("var(--type-other)");
  });

  it("cycle community colours and read predicates as phrases", () => {
    expect(communityColor(0)).toBe("var(--community-0)");
    expect(communityColor(13)).toBe("var(--community-3)");
    expect(communityColor(null)).toBe("var(--type-other)");
    expect(predicateLabel("PARTNERED_WITH")).toBe("partnered with");
  });
});

describe("layout", () => {
  it("is deterministic and keeps every node finite", () => {
    const a = computeLayout(nodes, edges, { width: 800, height: 600 });
    const b = computeLayout(nodes, edges, { width: 800, height: 600 });
    expect([...a]).toEqual([...b]);
    for (const { x, y } of a.values()) {
      expect(Number.isFinite(x)).toBe(true);
      expect(Number.isFinite(y)).toBe(true);
    }
    expect(a.size).toBe(nodes.length);
  });

  it("keeps nodes that were already placed near where they were", () => {
    const first = computeLayout(nodes, edges, { width: 800, height: 600 });
    const trimmed = computeLayout(
      nodes.slice(0, 10),
      edges.filter((e) => e.target !== "n10" && e.target !== "n11"),
      {
        width: 800,
        height: 600,
        previous: first,
        ticks: 20,
      },
    );
    const moved = Math.hypot(
      (trimmed.get("n0")?.x ?? 0) - (first.get("n0")?.x ?? 0),
      (trimmed.get("n0")?.y ?? 0) - (first.get("n0")?.y ?? 0),
    );
    expect(moved).toBeLessThan(80);
  });

  it("ignores edges that point outside the node set", () => {
    const layout = computeLayout(nodes, [...edges, { source: "n0", target: "ghost", weight: 1 }], {
      width: 400,
      height: 400,
    });
    expect(layout.has("ghost")).toBe(false);
  });

  it("sizes nodes by importance within a fixed range", () => {
    expect(nodeRadius(0, 10)).toBe(5);
    expect(nodeRadius(10, 10)).toBe(18);
    expect(nodeRadius(5, 0)).toBe(5);
  });
});

describe("view helpers", () => {
  it("fit a set of points into the viewport, centred", () => {
    const bounds = boundsOf(
      [
        { x: 0, y: 0 },
        { x: 400, y: 200 },
      ],
      0,
    );
    const fit = fitTransform(bounds, 800, 400, 3);
    expect(fit.k).toBe(2);
    expect(fit.x).toBe(0);
    expect(fit.y).toBe(0);
    expect(fitTransform(null, 800, 400)).toEqual({ k: 1, x: 0, y: 0 });
    expect(boundsOf([])).toBeNull();
  });

  it("find the neighbourhood of a selection", () => {
    expect([...neighbourhood("n0", edges)].length).toBe(12);
    expect([...neighbourhood("n5", edges)].sort()).toEqual(["n0", "n5"]);
    expect(neighbourhood(null, edges).size).toBe(0);
  });
});
