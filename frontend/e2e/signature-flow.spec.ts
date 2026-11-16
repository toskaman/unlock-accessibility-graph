import { expect, test } from "@playwright/test";

// The signature workflow on real imported data (Juvisy-sur-Orge, lift ASC3 "Voies 50 et 51 / souterrain nord").
test("simulate an outage, rank repairs, inspect evidence, restore", async ({ page }) => {
  await page.goto("/#station=Juvisy-sur-Orge");
  await expect(page.getByRole("heading", { name: "Juvisy-sur-Orge" })).toBeVisible();
  const confirmedBefore = Number(await page.locator(".counts .c-CONFIRMED_ACCESSIBLE .n").textContent());

  const lift = page.getByRole("button", { name: /Lift ASC\.PMR 4556 ASC3/ });
  await lift.click();
  await expect(page.locator(".liftbar h3")).toContainText("ASC3");
  await expect(page.locator(".deps")).toContainText("would be lost");

  await page.getByRole("button", { name: "Simulate outage" }).click();
  await expect(page.locator(".banner.sim")).toContainText("Published lift observations are unchanged");
  const confirmedOutage = Number(await page.locator(".counts .c-CONFIRMED_ACCESSIBLE .n").textContent());
  expect(confirmedOutage).toBeLessThan(confirmedBefore);
  await expect(page.locator(".pair.changed").first()).toBeVisible();

  // affected path + evidence from Relate
  await page.locator(".pair.changed").first().click();
  await expect(page.locator(".evidence")).toContainText("Source record");
  await expect(page.locator(".evidence .chain .node.lift").first()).toBeVisible();

  // ranking: the simulated lift restores exactly what the outage removed
  const top = page.locator("button.cand").first();
  await expect(top).toContainText("Simulated");
  const gain = Number((await top.locator(".gain strong").textContent())!.replace("+", ""));
  expect(gain).toBe(confirmedBefore - confirmedOutage);
  await top.click();
  await expect(page.getByRole("tab", { name: "With proposed repair" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".counts .c-CONFIRMED_ACCESSIBLE .n")).toHaveText(String(confirmedBefore));
  await expect(page.locator(".analyst")).toContainText("Calculated");

  // export
  const dl = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export report" }).click();
  expect((await dl).suggestedFilename()).toMatch(/^unlock-scn-.*\.json$/);

  // restore baseline -> identical to the start
  await page.getByRole("button", { name: "Restore published status" }).click();
  await expect(page.getByRole("tab", { name: "Published status" })).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".counts .c-CONFIRMED_ACCESSIBLE .n")).toHaveText(String(confirmedBefore));
});

test("keyboard: lifts are focusable buttons and the graph inspector opens", async ({ page }) => {
  await page.goto("/#station=Juvisy-sur-Orge");
  const lift = page.locator(".lift").first();
  await lift.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".liftbar h3")).toBeVisible();
  await page.getByRole("button", { name: "Inspect the graph" }).click();
  await expect(page.getByRole("dialog")).toContainText("Inside the Relate store");
  await expect(page.getByRole("dialog")).toContainText("ACYCLIC");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("API errors are explained, not swallowed", async ({ page }) => {
  await page.route("**/api/network/stations/**", (r) => r.fulfill({ status: 404, body: JSON.stringify({ detail: "Unknown station" }) }));
  await page.goto("/#station=Juvisy-sur-Orge");
  await expect(page.getByRole("alert")).toContainText("Unknown station");
});

test("outage report → graph-grounded lift → simulated impact; ambiguous reports are not guessed", async ({ page }) => {
  await page.goto("/#station=Paris%20Gare%20du%20Nord");
  await expect(page.locator(".section-svg")).toBeVisible();
  const before = Number(await page.locator(".counts .c-CONFIRMED_ACCESSIBLE .n").textContent());
  await page.getByRole("textbox", { name: /outage report/i }).or(page.locator(".report textarea")).first().fill("Juvisy : ascenseur quai 50/51 HS depuis ce matin");
  await page.getByRole("button", { name: "Find the lift" }).click();
  await expect(page.locator(".resolution")).toContainText("ASC3");
  await expect(page.locator(".resolution")).toContainText("SERVES edge");
  await page.getByRole("button", { name: "Simulate this outage" }).click();
  await expect(page.getByRole("heading", { name: "Juvisy-sur-Orge" })).toBeVisible();
  await expect(page.locator(".banner.sim")).toBeVisible();
  const after = Number(await page.locator(".counts .c-CONFIRMED_ACCESSIBLE .n").textContent());
  expect(after).toBe(before - 21);
  await page.locator(".chip").filter({ hasText: "Pontoise" }).click();
  await expect(page.locator(".resolution")).toContainText("won't guess");
  await expect(page.locator(".resolution .cands li")).toHaveCount(4);
  await page.getByRole("tab", { name: "Lifts you can't lose" }).click();
  await expect(page.locator(".critical")).toContainText("single point of failure");
});
