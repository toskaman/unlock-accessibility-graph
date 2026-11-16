import { expect, test } from "@playwright/test";

// Whole-region mode on the real committed snapshot: numbers come from the API, never hard-coded in the UI.
test("region: three views, journey check verified in Relate, station drill-down", async ({ page, request }) => {
  const ov = await (await request.get("/api/region/overview")).json();
  await page.goto("/");
  const fmt = (x: number) => x.toLocaleString("en-GB");
  await expect(page.locator(".hl-num")).toHaveText(fmt(ov.views.best.confirmed));
  await expect(page.locator(".frozen")).toContainText(`${ov.feed.lift_messages_stale_days} days`);
  await page.getByRole("tab", { name: "PRIM outage feed" }).click();
  await expect(page.locator(".hl-num")).toHaveText(fmt(ov.views.feed.confirmed));

  await page.getByRole("tab", { name: "Best available status" }).click();
  await page.getByRole("button", { name: "Rosa Parks → Juvisy" }).click();
  await expect(page.locator(".jverdict")).toBeVisible();
  await expect(page.locator(".jresult")).toContainText("Every leg re-checked in Relate");
  await expect(page.locator(".legs li").first()).toBeVisible();

  await page.getByRole("tab", { name: "Stale messages" }).click();
  await page.locator(".right .rank button").first().click();
  await expect(page.locator(".stationcard")).toContainText("SNCF's hourly feed");
});

test("region -> inside the station", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "Repairs that matter" }).click();
  await page.getByRole("button", { name: "Inside a station" }).click();
  await expect(page.locator(".report")).toBeVisible();
  await page.getByRole("button", { name: "Whole region" }).click();
  await expect(page.locator(".hl-num")).toBeVisible();
});
