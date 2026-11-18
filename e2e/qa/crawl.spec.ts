/**
 * Exploratory QA crawl: every page at desktop and mobile widths, signed in as the demo owner.
 *
 * A page fails on console errors, uncaught exceptions, failed or 4xx/5xx requests, sideways
 * scrolling, broken internal links and serious or critical axe violations (WCAG 2 A and AA).
 * A full-page capture of every page lands in e2e/.qa/ for a visual review.
 */
import { mkdirSync } from "node:fs";
import path from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { PROJECT, apiGet, settle, signIn } from "../helpers";

const OUT = path.resolve(__dirname, "../.qa");
mkdirSync(OUT, { recursive: true });

const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 },
] as const;

const SETTINGS_TABS = ["General", "Members", "API keys", "Activity"];

type Crawl = { page: Page; viewport: string; problems: string[]; links: Set<string> };

function watch(page: Page, viewport: string): Crawl {
  const crawl: Crawl = { page, viewport, problems: [], links: new Set() };
  page.on("console", (message) => {
    if (message.type() === "error") crawl.problems.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => crawl.problems.push(`uncaught: ${error.message}`));
  page.on("requestfailed", (request) => {
    const reason = request.failure()?.errorText ?? "";
    // Aborted requests are navigations away or cancelled queries, not failures.
    if (!reason.includes("ERR_ABORTED"))
      crawl.problems.push(`request failed: ${request.url()} ${reason}`);
  });
  page.on("response", (response) => {
    if (response.status() >= 400)
      crawl.problems.push(`HTTP ${response.status()}: ${response.url()}`);
  });
  return crawl;
}

async function inspect(crawl: Crawl, name: string): Promise<void> {
  const { page } = crawl;
  await settle(page);
  // The app shell scrolls inside <main>, so sideways overflow can hide there too.
  const overflow = await page.evaluate(() => {
    const outer = document.documentElement.scrollWidth - window.innerWidth;
    const main = document.querySelector("main");
    return Math.max(outer, main ? main.scrollWidth - main.clientWidth : 0);
  });
  if (overflow > 1) crawl.problems.push(`${name}: scrolls sideways by ${overflow}px`);

  const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  for (const violation of axe.violations) {
    if (violation.impact !== "serious" && violation.impact !== "critical") continue;
    const nodes = violation.nodes
      .slice(0, 3)
      .map((node) => node.target.join(" "))
      .join(" | ");
    crawl.problems.push(`${name}: axe ${violation.id} (${violation.impact}) at ${nodes}`);
  }

  const hrefs = await page.$$eval('a[href^="/"]', (anchors) =>
    anchors.map((a) => a.getAttribute("href") ?? ""),
  );
  for (const href of hrefs) crawl.links.add(href.split("#")[0] ?? href);
  await page.screenshot({ path: path.join(OUT, `${crawl.viewport}-${name}.png`), fullPage: true });
}

async function visit(crawl: Crawl, name: string, url: string, ready?: string): Promise<void> {
  const response = await crawl.page.goto(url);
  expect(response?.status(), url).toBeLessThan(400);
  // Scoped to the page content: on phones the sidebar (and its links) is off screen.
  if (ready) await expect(crawl.page.getByRole("main").getByText(ready).first()).toBeVisible();
  await inspect(crawl, name);
}

for (const viewport of VIEWPORTS) {
  test.describe(`${viewport.name} ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("signed-out pages", async ({ page }) => {
      const crawl = watch(page, viewport.name);
      await visit(crawl, "sign-in", "/login", "Welcome back");
      expect(crawl.problems).toEqual([]);
    });

    test("every project page", async ({ page }) => {
      test.setTimeout(300_000);
      await signIn(page, "owner");
      const crawl = watch(page, viewport.name);
      const base = `/p/${PROJECT}`;
      const documents = await apiGet<{ items: { id: string }[] }>(page, "/documents?limit=1");
      const communities = await apiGet<{ items: { id: string }[] }>(
        page,
        "/communities?level=0&limit=2",
      );
      const entities = await apiGet<{ items: { id: string; name: string }[] }>(
        page,
        "/graph/entities?q=Northgate&limit=10",
      );
      const focus = entities.items.find((e) => e.name === "Northgate Sensors");
      expect(documents.items[0] && communities.items[0] && focus, "seeded").toBeTruthy();

      await visit(crawl, "overview", base, "Entities by type");
      await visit(crawl, "documents", `${base}/documents`, "Graph build");
      await visit(
        crawl,
        "document",
        `${base}/documents/${documents.items[0]!.id}`,
        "Strongest entities",
      );
      await visit(crawl, "graph", `${base}/graph`, "Graph explorer");
      await expect(page.getByRole("button", { name: /^Helios Robotics, / })).toBeVisible();
      await page.getByRole("button", { name: /^Helios Robotics, / }).focus();
      await page.keyboard.press("Enter");
      await expect(page.getByRole("heading", { name: "Source passages" })).toBeVisible();
      await inspect(crawl, "graph-selected");
      await visit(crawl, "graph-focus", `${base}/graph?focus=${focus!.id}`, "Neighbourhood of");
      await visit(crawl, "entities", `${base}/entities`, "Select a row");
      await page.getByRole("button", { name: "Helios Robotics" }).first().click();
      await expect(page.getByRole("heading", { name: "Source passages" })).toBeVisible();
      await inspect(crawl, "entity-selected");
      await visit(crawl, "communities", `${base}/communities`, "Findings");
      await visit(
        crawl,
        "community",
        `${base}/communities?c=${communities.items[1]?.id ?? communities.items[0]!.id}`,
        "Members",
      );
      await visit(crawl, "playground", `${base}/playground`, "Ask the graph");
      await page.getByLabel("Question").fill("Who founded Helios Robotics?");
      await page.getByRole("button", { name: "Ask" }).click();
      await expect(page.getByTestId("answer")).toBeVisible();
      await inspect(crawl, "playground-answer");
      await visit(crawl, "settings", `${base}/settings`, "Graph pipeline");
      for (const tab of SETTINGS_TABS) {
        await page.getByRole("tab", { name: tab }).click();
        await inspect(crawl, `settings-${tab.toLowerCase().replace(" ", "-")}`);
      }

      for (const link of crawl.links) {
        const response = await page.request.get(link);
        if (response.status() >= 400)
          crawl.problems.push(`broken link: ${link} (${response.status()})`);
      }
      expect(crawl.problems).toEqual([]);
    });
  });
}
