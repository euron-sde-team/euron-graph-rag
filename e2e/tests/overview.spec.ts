import { expect, test } from "@playwright/test";

import { PROJECT, apiGet, signIn } from "../helpers";

type Overview = {
  counts: { entities: number; relations: number; communities: number; documents: number };
};

test("the overview reports the graph the demo built", async ({ page }) => {
  await signIn(page, "owner");
  const overview = await apiGet<Overview>(page, "/overview");
  expect(overview.counts.documents).toBeGreaterThanOrEqual(14);
  expect(overview.counts.entities).toBeGreaterThan(40);
  await page.goto(`/p/${PROJECT}`);
  await expect(page.getByRole("heading", { name: "Entities by type" })).toBeVisible();
  await expect(page.getByRole("group", { name: /The graph at a glance/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /Helios Robotics, Organization/ })).toBeVisible();
  await expect(page.getByText("Graph build").first()).toBeVisible();
  await expect(page.getByText("Completed").first()).toBeVisible();
});

test("the sidebar pages are one click apart", async ({ page }) => {
  await signIn(page, "owner");
  const nav = page.getByRole("navigation", { name: "Project" });
  for (const [name, heading] of [
    ["Documents", "Documents"],
    ["Graph explorer", "Graph explorer"],
    ["Entities", "Entities"],
    ["Communities", "Communities"],
    ["Playground", "Query playground"],
  ] as const) {
    await nav.getByRole("link", { name }).click();
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
  }
});
