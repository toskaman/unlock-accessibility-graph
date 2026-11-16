import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// An accessibility tool must be accessible itself: no serious or critical WCAG 2.1 A/AA violation (axe-core).
const scan = async (page: import("@playwright/test").Page) => {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .exclude(".maplibregl-canvas").analyze();
  const bad = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  if (bad.length) console.log(JSON.stringify(bad.map((v) => ({ id: v.id, impact: v.impact, n: v.nodes.length, t: v.nodes.slice(0, 3).map((x) => x.target) })), null, 1));
  return bad;
};

test("a11y: whole-region mode, journey result and station card", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".hl-num")).toBeVisible();
  expect(await scan(page)).toEqual([]);
  await page.getByRole("button", { name: "Rosa Parks → Juvisy" }).click();
  await expect(page.locator(".jverdict")).toBeVisible();
  await page.getByRole("tab", { name: "Repairs that matter" }).click();
  await page.locator(".right .rank button").first().click();
  await expect(page.locator(".stationcard")).toBeVisible();
  expect(await scan(page)).toEqual([]);
});

test("a11y: inside a station", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Inside a station" }).click();
  await expect(page.locator(".report")).toBeVisible();
  expect(await scan(page)).toEqual([]);
});
