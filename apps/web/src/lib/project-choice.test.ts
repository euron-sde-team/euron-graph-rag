import { describe, expect, it } from "vitest";

import { pickProject } from "@/lib/project-choice";
import type { ProjectSummary } from "@/lib/types";

const project = (slug: string, entities: number): ProjectSummary => ({
  id: slug,
  slug,
  name: slug,
  role: "owner",
  document_count: entities > 0 ? 3 : 0,
  entity_count: entities,
  member_count: 1,
});

describe("pickProject", () => {
  const projects = [project("alpha", 0), project("port-intelligence", 55), project("beta", 9)];

  it("returns the last project when the person still belongs to it", () => {
    expect(pickProject(projects, "beta")).toBe("beta");
  });

  it("falls back to the project with the most entities", () => {
    expect(pickProject(projects, "gone")).toBe("port-intelligence");
    expect(pickProject(projects, null)).toBe("port-intelligence");
  });

  it("returns null without projects", () => {
    expect(pickProject([], "beta")).toBeNull();
  });
});
