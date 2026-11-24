// Fresh Devpost/README screenshots from a deployed demo: node scripts/shot-devpost.mjs [url]
// Overwrites docs/media/*.png. One failure never stops the remaining shots.
import { chromium } from "playwright";
const base = (process.argv[2] || "https://toskaman.github.io/unlock-accessibility-graph/").replace(/\/$/, "");
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
const shots = [];
async function shot(name, fn) {
  try {
    await fn();
    await p.getByRole("button", { name: "Skip" }).click().catch(() => {});
    await p.waitForTimeout(1200);
    await p.getByRole("button", { name: "Skip" }).click().catch(() => {});
    await p.waitForTimeout(500);
    await p.screenshot({ path: `../docs/media/${name}.png` });
    shots.push(`${name}: OK`);
  } catch (e) {
    shots.push(`${name}: FAILED (${String(e).split("\n")[0].slice(0, 160)})`);
  }
}
async function fresh() {
  await p.goto(`${base}/`, { waitUntil: "networkidle", timeout: 90000 });
  await p.waitForSelector('[data-relate="ready"]', { timeout: 90000 });
  await p.getByRole("button", { name: "Skip" }).click().catch(() => {});
}
await p.goto(`${base}/`, { waitUntil: "networkidle", timeout: 90000 });
await p.waitForSelector('[data-relate="ready"]', { timeout: 90000 });
await p.evaluate(() => document.fonts?.ready);
await p.getByRole("button", { name: "Skip" }).click().catch(() => {});
await p.waitForTimeout(500);
await shot("region-overview", async () => {
  await p.getByRole("button", { name: "Show me the map" }).click();
  await p.locator(".map-wrap, canvas").first().scrollIntoViewIfNeeded();
});
await shot("region-journey", async () => {
  await p.getByRole("button", { name: "Rosa Parks → Juvisy" }).click();
  await p.getByRole("button", { name: "Check the journey" }).click();
  await p.waitForSelector(".jverdict, .journey-result, .verdict", { timeout: 60000 });
});
await shot("region-reach", async () => {
  await fresh();
  await p.getByRole("button", { name: "Show me the map" }).click().catch(() => {});
  await p.locator(".right .rank button, .repairs button").first().click().catch(() => {});
  await p.waitForTimeout(2000);
  await p.locator(".map-wrap, canvas").first().scrollIntoViewIfNeeded();
});
await shot("region-stale", async () => {
  await fresh();
  await p.getByRole("tab", { name: "Stale messages" }).click();
  await p.waitForTimeout(2000);
});
await shot("regions-compare", async () => {
  await fresh();
  await p.getByRole("button", { name: "Compare all regions" }).click();
  await p.waitForSelector(".compare table, table.compare", { timeout: 30000 });
  await p.waitForTimeout(2000);
});
await shot("region-history", async () => {
  await fresh();
  await p.getByRole("tab", { name: "History" }).click();
  await p.waitForTimeout(2500);
});
await shot("bulletin", async () => {
  await fresh();
  const link = p.getByRole("link", { name: "Today's maintenance bulletin" });
  const href = await link.getAttribute("href");
  const [popup] = await Promise.all([
    p.context().waitForEvent("page", { timeout: 8000 }).catch(() => null),
    link.click(),
  ]);
  if (popup) {
    await popup.waitForLoadState("networkidle", { timeout: 60000 }).catch(() => {});
    const url = popup.url();
    await popup.close();
    await p.goto(url, { waitUntil: "networkidle", timeout: 60000 });
  }
  await p.waitForTimeout(2000);
  shots.push(`bulletin href was: ${href}`);
});
console.log(shots.join("\n"));
await b.close();
