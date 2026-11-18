import { expect, test } from "@playwright/test";

import { PROJECT, signIn } from "../helpers";

const GRAPH = `/p/${PROJECT}/graph`;
const NODES = /, \d+ connections$/;

test("selecting a node shows its relations and the passages behind them", async ({ page }) => {
  await signIn(page, "owner");
  await page.goto(GRAPH);
  const helios = page.getByRole("button", { name: /^Helios Robotics, Organization/ });
  await expect(helios).toBeVisible();
  await helios.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Helios Robotics", level: 2 })).toBeVisible();
  await expect(page.getByText("acquired").first()).toBeVisible();
  await expect(page.getByText("Northgate Sensors").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Source passages" })).toBeVisible();
  await expect(page.getByRole("link", { name: /company profile/ }).first()).toBeVisible();
});

test("filters narrow the graph by type and by text", async ({ page }) => {
  await signIn(page, "owner");
  await page.goto(GRAPH);
  await expect(page.getByRole("button", { name: NODES }).first()).toBeVisible();
  const all = await page.getByRole("button", { name: NODES }).count();
  await page.getByRole("button", { name: /^Person/ }).click();
  await expect
    .poll(async () => page.getByRole("button", { name: /, Person, / }).count())
    .toBeGreaterThan(3);
  expect(await page.getByRole("button", { name: /, Organization, / }).count()).toBe(0);
  await page.getByRole("button", { name: /^Person/ }).click();
  await page.getByLabel("Filter entities").fill("Voltaic");
  await expect(page.getByRole("button", { name: /^Voltaic Cells/ })).toBeVisible();
  await expect
    .poll(async () => page.getByRole("button", { name: NODES }).count())
    .toBeLessThan(all);
});

test("focusing an entity shows only its neighbourhood, and the whole graph comes back", async ({
  page,
}) => {
  await signIn(page, "owner");
  await page.goto(GRAPH);
  await page.getByRole("button", { name: /^Northgate Sensors, / }).dblclick();
  await expect(page.getByText(/Neighbourhood of Northgate Sensors/)).toBeVisible();
  await expect(page).toHaveURL(/focus=/);
  const near = await page.getByRole("button", { name: NODES }).count();
  expect(near).toBeGreaterThan(3);
  await page.getByRole("button", { name: "Show the whole graph" }).click();
  await expect
    .poll(async () => page.getByRole("button", { name: NODES }).count())
    .toBeGreaterThan(near);
});

test("colouring by community adds a legend of community names", async ({ page }) => {
  await signIn(page, "owner");
  await page.goto(GRAPH);
  await page.getByLabel("Colour by").selectOption("community");
  await expect(
    page.getByRole("list", { name: "Communities" }).getByRole("listitem").first(),
  ).toBeVisible();
});
