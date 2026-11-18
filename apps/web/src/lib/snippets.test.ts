import { describe, expect, it } from "vitest";

import { snippets } from "./snippets";

describe("snippets", () => {
  const input = { apiUrl: "http://localhost:8200", project: "port-intelligence", key: "grk_demo" };

  it("point every example at the project's query endpoint with the key", () => {
    const { curl, python, node } = snippets(input);
    for (const text of [curl, python, node]) {
      expect(text).toContain("http://localhost:8200/api/v1/projects/port-intelligence/query");
      expect(text).toContain("Bearer grk_demo");
      expect(text).toContain("hybrid");
    }
  });

  it("keep the shell command continuous across lines", () => {
    const lines = snippets(input).curl.split("\n");
    expect(lines.slice(0, -1).every((line) => line.endsWith("\\"))).toBe(true);
  });
});
