import { expect, test, type Page } from "@playwright/test";

import { PROJECT, signIn } from "../helpers";

async function ask(page: Page, mode: string, question: string) {
  await page.goto(`/p/${PROJECT}/playground`);
  await page.getByRole("radio", { name: mode }).click();
  await page.getByLabel("Question").fill(question);
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByTestId("answer")).toBeVisible();
}

test("a local question is answered from cited passages and shows the subgraph used", async ({
  page,
}) => {
  await signIn(page, "owner");
  await ask(page, "Local", "Who founded Helios Robotics?");
  await expect(page.getByTestId("answer")).toContainText("Mira Okafor");
  await expect(page.getByRole("link", { name: /^Source 1/ }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: /Sources \(\d+ cited/ })).toBeVisible();
  await expect(page.getByRole("group", { name: /Entities and relations used/ })).toBeVisible();
  await expect(page.getByText("Find passages")).toBeVisible();
  await expect(page.getByText("Walk the graph")).toBeVisible();
});

test("a global question maps community reports instead of passages", async ({ page }) => {
  await signIn(page, "owner");
  await ask(page, "Global", "How is predictive maintenance used in port terminals?");
  await expect(page.getByText("Map: points per report")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Communities used" })).toBeVisible();
  await expect(page.getByText("Community report:").first()).toBeVisible();
});

test("a hybrid question cites both passages and community reports", async ({ page }) => {
  await signIn(page, "owner");
  await ask(page, "Hybrid", "How does Helios Robotics depend on its suppliers and investors?");
  await expect(page.getByText("Community report:").first()).toBeVisible();
  await expect(page.getByText(/company profile/).first()).toBeVisible();
});

test("a citation chip jumps to its source card", async ({ page }) => {
  await signIn(page, "owner");
  await ask(page, "Local", "Where is Kestrel Analytics based?");
  await page.getByTestId("answer").getByRole("link").first().click();
  await expect(page).toHaveURL(/#source-1$/);
});

test("past questions can be reopened from the history", async ({ page }) => {
  await signIn(page, "owner");
  await page.goto(`/p/${PROJECT}/playground`);
  const recent = page.getByRole("button", { name: /Who is the CEO of Voltaic Cells\?/ }).first();
  await expect(recent).toBeVisible();
  await recent.click();
  await expect(page.getByTestId("answer")).toBeVisible();
  await expect(page.getByLabel("Question")).toHaveValue(/CEO of Voltaic Cells/);
});
