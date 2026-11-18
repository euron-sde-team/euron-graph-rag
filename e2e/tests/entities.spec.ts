import { expect, test } from "@playwright/test";

import { PROJECT, signIn } from "../helpers";

test("search finds an entity and its detail lists relations and sources", async ({ page }) => {
  await signIn(page, "owner");
  await page.goto(`/p/${PROJECT}/entities`);
  await page.getByLabel("Search entities").fill("Kestrel");
  await page.getByRole("button", { name: "Kestrel Analytics" }).click();
  await expect(page.getByRole("heading", { name: "Kestrel Analytics", level: 2 })).toBeVisible();
  await expect(page.getByText("developed").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Source passages" })).toBeVisible();
});

test("the type filter and sorting change the table", async ({ page }) => {
  await signIn(page, "owner");
  await page.goto(`/p/${PROJECT}/entities`);
  await page.getByLabel("Type").selectOption("PERSON");
  await expect(page.getByRole("cell", { name: "Mira Okafor" })).toBeVisible();
  await expect(page.getByRole("cell", { name: "Helios Robotics" })).toHaveCount(0);
  await page.getByLabel("Sort").selectOption("name");
  await expect(page.getByRole("table").getByRole("button").first()).toHaveText("Amara Nwosu");
});

test("the duplicates tab says there is nothing left to merge once a build has run", async ({
  page,
}) => {
  await signIn(page, "owner");
  await page.goto(`/p/${PROJECT}/entities`);
  await page.getByRole("tab", { name: /Duplicates/ }).click();
  await expect(page.getByText("No duplicates left")).toBeVisible();
});
