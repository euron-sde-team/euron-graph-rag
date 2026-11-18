import { expect, test } from "@playwright/test";

import { PROJECT, signIn } from "../helpers";

const NOTE = `# Orbital Freight pilot

Orbital Freight is a drone logistics company based in Lisbon. Sofia Marques founded Orbital Freight in 2022.
Orbital Freight partnered with Helios Robotics to move containers at the Port of Rotterdam Authority.`;

test("the pipeline lists every demo note as ready", async ({ page }) => {
  await signIn(page, "owner");
  await page.goto(`/p/${PROJECT}/documents`);
  const table = page.getByRole("table");
  await expect(table.getByRole("link", { name: /Helios Robotics: company profile/ })).toBeVisible();
  await expect(table.getByText("Ready").first()).toBeVisible();
  await page.getByLabel("Search documents").fill("Voltaic");
  await expect(table.getByRole("row")).toHaveCount(2);
});

test("a pasted note travels the whole pipeline into the graph, and deleting it removes its facts", async ({
  page,
}) => {
  test.setTimeout(240_000);
  await signIn(page, "editor");
  await page.goto(`/p/${PROJECT}/documents`);
  await page.getByRole("button", { name: "Add documents" }).click();
  await page.getByRole("tab", { name: "Text" }).click();
  await page.getByLabel("Title").fill("Orbital Freight pilot");
  await page.getByLabel("Text", { exact: true }).fill(NOTE);
  await page.getByRole("button", { name: "Add text" }).click();
  const row = page.getByRole("row", { name: /Orbital Freight pilot/ });
  await expect(row).toBeVisible();
  await expect(row.getByText("Ready")).toBeVisible({ timeout: 120_000 });

  await row.getByRole("link", { name: /Orbital Freight pilot/ }).click();
  await expect(page.getByRole("heading", { name: "Passages" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Strongest entities" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Orbital Freight/ }).first()).toBeVisible();

  await page.goto(`/p/${PROJECT}/entities`);
  await page.getByLabel("Search entities").fill("Orbital Freight");
  await expect(page.getByRole("button", { name: "Orbital Freight" })).toBeVisible();

  await page.goto(`/p/${PROJECT}/documents`);
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "Actions for Orbital Freight pilot" }).click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await expect(page.getByRole("row", { name: /Orbital Freight pilot/ })).toHaveCount(0);
  await page.goto(`/p/${PROJECT}/entities`);
  await page.getByLabel("Search entities").fill("Orbital Freight");
  await expect(page.getByText("No entities match")).toBeVisible();
});

test("a document opens with its passages and strongest entities", async ({ page }) => {
  await signIn(page, "owner");
  await page.goto(`/p/${PROJECT}/documents`);
  await page.getByRole("link", { name: /Atlas Platform and the Orion Engine/ }).click();
  await expect(
    page.getByRole("heading", { name: "Atlas Platform and the Orion Engine", level: 1 }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Passages" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Helios Robotics/ }).first()).toBeVisible();
});
