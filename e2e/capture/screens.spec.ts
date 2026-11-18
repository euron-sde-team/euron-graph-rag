/**
 * README screenshots (1440x900 at 2x) and tour frames, from the seeded demo project.
 * Every image shows the real stack: nothing here is mocked.
 */
import { mkdirSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { PROJECT, apiGet, settle, signIn } from "../helpers";

const SHOTS = path.resolve(__dirname, "../../docs/assets/screenshots");
const FRAMES = path.resolve(__dirname, "../.capture/frames");
mkdirSync(SHOTS, { recursive: true });
mkdirSync(FRAMES, { recursive: true });

const BASE = `/p/${PROJECT}`;
let frame = 0;

async function shot(page: Page, name: string): Promise<void> {
  await settle(page);
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`) });
}

async function tourFrame(page: Page, holdMs = 1800): Promise<void> {
  frame += 1;
  const file = path.join(FRAMES, `${String(frame).padStart(3, "0")}-${holdMs}.png`);
  await page.screenshot({ path: file, scale: "css" });
}

async function ask(page: Page, mode: string, question: string): Promise<void> {
  await page.goto(`${BASE}/playground`);
  await page.getByRole("radio", { name: mode }).click();
  await page.getByLabel("Question").fill(question);
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page.getByTestId("answer")).toBeVisible();
  await expect(page.getByRole("heading", { name: /Sources \(/ })).toBeVisible();
}

test.describe.configure({ mode: "serial" });
// Captures run on a busy laptop as often as on CI: allow slow answers rather than flake.
test.setTimeout(300_000);

test("sign-in page", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("Your documents, as a graph.")).toBeVisible();
  await shot(page, "01-sign-in");
  await tourFrame(page, 1400);
});

test("overview, the explorer, entities, communities, documents and settings", async ({ page }) => {
  await signIn(page, "owner");

  await page.goto(BASE);
  await expect(page.getByRole("heading", { name: "Entities by type" })).toBeVisible();
  await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible();
  await expect(page.locator(".recharts-area").first()).toBeVisible();
  await shot(page, "02-overview");
  await tourFrame(page, 2600);

  await page.goto(`${BASE}/graph`);
  const helios = page.getByRole("button", { name: /^Helios Robotics, Organization/ });
  await expect(helios).toBeVisible();
  await helios.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Source passages" })).toBeVisible();
  await page.mouse.move(5, 5);
  await shot(page, "03-graph-explorer");
  await tourFrame(page, 3000);

  await page.getByLabel("Colour by").selectOption("community");
  await expect(page.getByRole("list", { name: "Communities" })).toBeVisible();
  await shot(page, "04-graph-communities");
  await tourFrame(page, 2600);

  const northgate = await apiGet<{ items: { id: string }[] }>(
    page,
    "/graph/entities?q=Northgate&limit=1",
  );
  await page.goto(`${BASE}/graph?focus=${northgate.items[0]!.id}`);
  await expect(page.getByText(/Neighbourhood of Northgate Sensors/)).toBeVisible();
  await shot(page, "05-graph-neighbourhood");

  await page.goto(`${BASE}/entities`);
  await page.getByRole("button", { name: "Voltaic Cells" }).first().click();
  await expect(page.getByRole("heading", { name: "Voltaic Cells", level: 2 })).toBeVisible();
  await shot(page, "06-entities");
  await tourFrame(page, 2200);

  await page.goto(`${BASE}/communities`);
  await expect(page.getByRole("heading", { name: "Findings" })).toBeVisible();
  await page
    .getByRole("list", { name: "Community hierarchy" })
    .getByRole("button", { name: /^Expand / })
    .first()
    .click();
  await shot(page, "07-communities");
  await tourFrame(page, 2600);

  await page.goto(`${BASE}/documents`);
  await expect(page.getByRole("table").getByText("Ready").first()).toBeVisible();
  await shot(page, "08-documents");
  await tourFrame(page, 2200);
});

test("the query playground in all three modes", async ({ page }) => {
  await signIn(page, "owner");
  await ask(page, "Local", "Who founded Helios Robotics?");
  await expect(page.getByRole("group", { name: /Entities and relations used/ })).toBeVisible();
  await page.mouse.move(5, 5);
  await shot(page, "09-playground-local");
  await tourFrame(page, 3200);

  await ask(page, "Global", "How is predictive maintenance used in port terminals?");
  await expect(page.getByRole("heading", { name: "Communities used" })).toBeVisible();
  await shot(page, "10-playground-global");
  await tourFrame(page, 3000);

  await ask(page, "Hybrid", "How does Helios Robotics depend on its suppliers and investors?");
  await expect(page.getByRole("group", { name: /Entities and relations used/ })).toBeVisible();
  await page.mouse.move(5, 5);
  await shot(page, "11-playground-hybrid");
  await tourFrame(page, 3200);
});

test("a document with its passages, and the settings", async ({ page }) => {
  await signIn(page, "owner");
  const documents = await apiGet<{ items: { id: string; title: string }[] }>(
    page,
    "/documents?q=Atlas&limit=1",
  );
  await page.goto(`${BASE}/documents/${documents.items[0]!.id}`);
  await expect(page.getByRole("heading", { name: "Strongest entities" })).toBeVisible();
  await shot(page, "12-document");

  await page.goto(`${BASE}/settings`);
  await expect(page.getByRole("heading", { name: "Graph pipeline" })).toBeVisible();
  await shot(page, "13-settings");
  await tourFrame(page, 1800);
});
