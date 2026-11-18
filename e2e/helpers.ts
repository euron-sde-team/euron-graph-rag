import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { expect, type Page } from "@playwright/test";

export const API_URL = process.env.API_URL ?? "http://localhost:8200";
export const WEB_URL = process.env.WEB_URL ?? "http://localhost:3200";
export const PASSWORD = process.env.DEMO_PASSWORD ?? "";
export const PROJECT = "port-intelligence";

export const PEOPLE = {
  owner: { email: "maya.iyer@meridian-research.example", name: "Maya Iyer" },
  editor: { email: "lucas.moreau@meridian-research.example", name: "Lucas Moreau" },
  viewer: { email: "hana.takeda@meridian-research.example", name: "Hana Takeda" },
} as const;

export type Person = keyof typeof PEOPLE;

export function requirePassword(): string {
  if (!PASSWORD) throw new Error("Set DEMO_PASSWORD (make e2e reads it from deploy/compose/.env)");
  return PASSWORD;
}

const SESSIONS = path.resolve(__dirname, ".auth");

/** Sign in through the form, exactly as a person does. */
export async function signInWithForm(page: Page, who: Person = "owner"): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(PEOPLE[who].email);
  await page.getByLabel("Password").fill(requirePassword());
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(new RegExp(`/p/${PROJECT}`));
}

/**
 * A signed-in page for one demo person. The session cookie from the first form sign-in is
 * saved per role and reused by later tests: the API allows ten sign-ins a minute per
 * address, and the suites would otherwise trip that limit themselves. A stale cookie (after
 * `make down`) falls back to the form.
 */
export async function signIn(page: Page, who: Person = "owner"): Promise<void> {
  const saved = path.join(SESSIONS, `${who}.json`);
  if (existsSync(saved)) {
    await page.context().addCookies(JSON.parse(readFileSync(saved, "utf8")));
    await page.goto("/");
    await page.waitForURL(/\/(p\/[^/]+|login|welcome)/);
    if (page.url().includes(`/p/${PROJECT}`)) return;
    await page.context().clearCookies();
  }
  await signInWithForm(page, who);
  mkdirSync(SESSIONS, { recursive: true });
  writeFileSync(saved, JSON.stringify(await page.context().cookies()));
}

/** GET a project API path with the page's session; returns the parsed body. */
export async function apiGet<T>(page: Page, apiPath: string): Promise<T> {
  const response = await page.request.get(`${API_URL}/api/v1/projects/${PROJECT}${apiPath}`);
  expect(response.ok(), apiPath).toBeTruthy();
  return (await response.json()) as T;
}

/** Wait until the page has settled: no pending network, fonts ready, transitions finished. */
export async function settle(page: Page): Promise<void> {
  await page.waitForLoadState("networkidle");
  await page.evaluate(async () => {
    await document.fonts.ready;
    // Spinners and pulsing dots repeat forever; only wait for animations that end.
    const finite = document
      .getAnimations()
      .filter((animation) => animation.effect?.getTiming().iterations !== Infinity);
    await Promise.all(finite.map((animation) => animation.finished.catch(() => undefined)));
  });
}
