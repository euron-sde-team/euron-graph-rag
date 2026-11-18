import { expect, test } from "@playwright/test";

import { PROJECT, signIn } from "../helpers";

test("the owner reads members and activity and creates an API key with examples", async ({
  page,
}) => {
  await signIn(page, "owner");
  await page.goto(`/p/${PROJECT}/settings`);
  await expect(page.getByRole("heading", { name: "Graph pipeline" })).toBeVisible();

  await page.getByRole("tab", { name: "Members" }).click();
  await expect(page.getByText("Hana Takeda")).toBeVisible();

  await page.getByRole("tab", { name: "Activity" }).click();
  await expect(page.getByText(/added .* as/).first()).toBeVisible();

  await page.getByRole("tab", { name: "API keys" }).click();
  await page
    .getByRole("button", { name: /Create/ })
    .first()
    .click();
  await page.getByLabel("Name").fill("e2e key");
  await page.getByRole("button", { name: "Create key" }).click();
  await expect(page.getByText(/grk_/).first()).toBeVisible();
  await expect(page.getByRole("tab", { name: "curl" })).toBeVisible();
});

test("graph settings can be changed by the owner", async ({ page }) => {
  await signIn(page, "owner");
  await page.goto(`/p/${PROJECT}/settings`);
  await page.getByLabel("Resolution").fill("1.2");
  await page.getByRole("button", { name: "Save graph settings" }).click();
  await expect(page.getByText(/Graph settings saved/).first()).toBeVisible();
  await page.getByLabel("Resolution").fill("1");
  await page.getByRole("button", { name: "Save graph settings" }).click();
  await expect(page.getByText(/Graph settings saved/).first()).toBeVisible();
});
