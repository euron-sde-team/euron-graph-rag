import { expect, test } from "@playwright/test";

import { PROJECT, signIn } from "../helpers";

test("the hierarchy opens into sub-communities with reports and findings", async ({ page }) => {
  await signIn(page, "owner");
  await page.goto(`/p/${PROJECT}/communities`);
  const tree = page.getByRole("list", { name: "Community hierarchy" });
  await expect(tree).toBeVisible();
  await expect(page.getByRole("heading", { name: "Findings" })).toBeVisible();
  await tree
    .getByRole("button", { name: /^Expand / })
    .first()
    .click();
  const child = tree
    .locator("ul button[aria-current], ul > li button:not([aria-expanded])")
    .first();
  await expect(child).toBeVisible();
  await child.click();
  await expect(page).toHaveURL(/communities\?c=/);
  await expect(page.getByRole("heading", { name: "Members" })).toBeVisible();
});

test("a member links to its neighbourhood in the explorer", async ({ page }) => {
  await signIn(page, "owner");
  await page.goto(`/p/${PROJECT}/communities`);
  await page.getByRole("region", { name: "Members" }).getByRole("link").first().click();
  await expect(page).toHaveURL(/\/graph\?focus=/);
  await expect(page.getByText(/Neighbourhood of/)).toBeVisible();
});
