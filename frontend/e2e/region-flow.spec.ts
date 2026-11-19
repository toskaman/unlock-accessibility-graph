import { expect, test } from "@playwright/test";

// Whole-region mode on the real committed snapshot: numbers come from the API, never hard-coded in the UI.
test("region: three views, journey check verified in Relate, station drill-down", async ({ page, request }) => {
  const ov = await (await request.get("/api/region/overview")).json();
  await page.goto("/");
  const fmt = (x: number) => x.toLocaleString("en-GB");
  await expect(page.locator(".hl-num")).toHaveText(fmt(ov.views.best.confirmed));
  await expect(page.locator(".frozen")).toContainText(`${ov.feed.lift_messages_stale_days} days`);
  await page.getByRole("tab", { name: "What the official feed announces" }).click();
  await expect(page.locator(".hl-num")).toHaveText(fmt(ov.views.feed.confirmed));

  await page.getByRole("tab", { name: "What the operators say" }).click();
  await page.getByRole("button", { name: "Rosa Parks → Juvisy" }).click();
  await expect(page.locator(".jverdict")).toBeVisible();
  await expect(page.locator(".jresult")).toContainText("Every leg re-checked in Relate");
  await expect(page.locator(".legs li").first()).toBeVisible();

  await page.getByRole("tab", { name: "Stale messages" }).click();
  await page.locator(".right .rank button").first().click();
  // the stale message points at an SNCF lift (checked against SNCF's hourly feed) or a RATP one (IDFM lift status)
  await expect(page.locator(".stationcard")).toContainText(/SNCF's hourly feed|IDFM's lift status/);
});

test("region -> inside the station", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "Repairs that matter" }).click();
  await page.getByRole("button", { name: "Inside a station" }).click();
  await expect(page.locator(".report")).toBeVisible();
  await page.getByRole("button", { name: "Whole region" }).click();
  await expect(page.locator(".hl-num")).toBeVisible();
});

test("region: where can I go from here — reach recoloured and re-derived in Cypher", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "Repairs that matter" }).click();
  await page.locator(".right .rank button").first().click();
  await expect(page.locator(".reach-num")).toBeVisible();
  const card = page.locator(".reachbox");
  await expect(card).toContainText("Re-derived in Relate with Cypher");
  const name = (await page.locator(".stationcard h3").textContent())!.trim();
  const hits = await (await request.get(`/api/region/stations?q=${encodeURIComponent(name)}`)).json();
  const r = await (await request.get(`/api/region/reach?from=${hits[0].id}&view=best`)).json();
  await expect(page.locator(".reach-num")).toHaveText(r.counts.confirmed.toLocaleString("en-GB"));
  await expect(page.locator(".region-legend")).toContainText(`From ${name}`);
});

test("rider alerts: watch a usual trip, status from the API, kept in this browser", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Rosa Parks → Juvisy" }).click();
  await expect(page.locator(".jverdict")).toBeVisible();
  await page.getByRole("button", { name: /^Watch Rosa Parks/ }).click();
  const api = await (await request.post("/api/region/trips/check", { data: { trips: [{ from: "73798", to: "478505" }] } })).json();
  const label = { OK: "Step-free today", DETOUR: "Detour needed", AT_RISK: "At risk", CUT: "Cut today", NO_STEP_FREE_ROUTE: "No step-free route" }[api.trips[0].status as string]!;
  await expect(page.locator(".tw-list li").first()).toContainText(label);
  await page.reload();
  await expect(page.locator(".tw-list li").first()).toContainText("Rosa Parks → Juvisy");
  await page.getByRole("button", { name: "Remove Rosa Parks to Juvisy" }).click();
  await expect(page.locator(".tw-list li")).toHaveCount(0);
  const b = await request.get("/api/region/bulletin.html");
  expect(b.ok()).toBeTruthy();
  expect(await b.text()).toContain("Fix first");
});

test("language: English / French switch in the header, remembered after a reload", async ({ page, request }) => {
  const ov = await (await request.get("/api/region/overview")).json();
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Can I get there in a wheelchair?" })).toBeVisible();
  await page.getByRole("button", { name: "FR — Français" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "fr");
  await expect(page.getByRole("heading", { name: "Puis-je y aller en fauteuil ?" })).toBeVisible();
  await expect(page.locator(".hl-num")).toHaveText(ov.views.best.confirmed.toLocaleString("fr-FR"));
  await page.getByRole("button", { name: "Rosa Parks → Juvisy" }).click();
  await expect(page.locator(".jresult")).toContainText("Chaque tronçon revérifié dans Relate");
  await page.reload();
  await expect(page.getByRole("tab", { name: "Réparations utiles" })).toBeVisible();
  await page.getByRole("button", { name: "EN — English" }).click();
  await expect(page.getByRole("tab", { name: "Repairs that matter" })).toBeVisible();
});

test("field report: written to the shared graph, read back and compared with the official status", async ({ page, request }) => {
  await page.goto("/");
  await page.getByRole("tab", { name: "Repairs that matter" }).click();
  await page.locator(".right .rank button").first().click();
  const card = page.locator(".stationcard");
  await card.getByText("Report what you see").click();
  await card.getByLabel("Out of service").check();
  await card.getByLabel("Note (optional)").fill("e2e test");
  await card.getByRole("button", { name: "Send the report" }).click();
  await expect(card.getByRole("status")).toContainText("Report saved");
  await expect(card.locator(".freports .olist li").first()).toContainText("seen out of service");
  const api = await (await request.get("/api/region/reports")).json();
  expect(api.reports.some((r: { note: string }) => r.note === "e2e test")).toBeTruthy();
});

test("ask an AI agent: recorded sessions replayed, the rider's trip opened on the map", async ({ page }) => {
  await page.goto("/");
  const panel = page.locator(".agentreplay");
  await expect(panel.getByRole("heading", { name: "Ask an AI agent" })).toBeVisible();
  await panel.getByRole("button", { name: "Agent 2 reads it back" }).click();
  await expect(panel.locator(".ar-call code").first()).toContainText("field_reports");
  await expect(panel.locator(".ar-a")).toContainText("Juvisy");
  await panel.getByRole("button", { name: "A rider asks, in French" }).click();
  await panel.getByRole("button", { name: "Check this trip on the map" }).click();
  await expect(page.locator(".jresult")).toContainText("Rosa Parks → Juvisy");
});

test("the map as a list and the easy-read version", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Easy read" }).click();
  await expect(page.locator("#easyread")).toContainText("A cross: you cannot.");
  await page.getByRole("button", { name: "Show as a list" }).click();
  const list = page.locator("#maplist");
  await expect(list.getByRole("heading", { name: "Stations by state" })).toBeVisible();
  await list.locator("details").first().locator("li button").first().click();
  await expect(page.locator(".stationcard")).toBeVisible();
  await expect(list.getByRole("heading")).toContainText("Where you can go from");
});
