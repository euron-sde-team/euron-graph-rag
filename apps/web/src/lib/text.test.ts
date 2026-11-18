import { describe, expect, it } from "vitest";

import { answerParts, citationMarkers, highlightParts } from "./text";

describe("highlightParts", () => {
  it("marks every occurrence, longest term first, ignoring case", () => {
    const parts = highlightParts("Helios Robotics hired helios staff", [
      "Helios",
      "Helios Robotics",
    ]);
    expect(parts.filter((p) => p.match).map((p) => p.text)).toEqual(["Helios Robotics", "helios"]);
    expect(parts.map((p) => p.text).join("")).toBe("Helios Robotics hired helios staff");
  });

  it("escapes pattern characters and ignores one-letter terms", () => {
    expect(highlightParts("a (b) c", ["(b)"]).some((p) => p.match)).toBe(true);
    expect(highlightParts("abc", ["a"])).toEqual([{ text: "abc", match: false }]);
  });
});

describe("citations in an answer", () => {
  it("lists markers once, in order", () => {
    expect(citationMarkers("A [2]. B [1] [2].")).toEqual([2, 1]);
    expect(citationMarkers("nothing")).toEqual([]);
  });

  it("splits text from markers without losing anything", () => {
    const parts = answerParts("Founded in 2018 [1]. Led by Mira [3].");
    expect(parts.filter((p) => p.kind === "cite")).toEqual([
      { kind: "cite", n: 1 },
      { kind: "cite", n: 3 },
    ]);
    expect(parts.map((p) => (p.kind === "text" ? p.text : `[${p.n}]`)).join("")).toBe(
      "Founded in 2018 [1]. Led by Mira [3].",
    );
  });
});
