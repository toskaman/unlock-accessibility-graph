// Region-mode screenshots for the README: node scripts/shot-region.mjs [baseUrl]
import { chromium } from "playwright";
const base = process.argv[2] || "http://localhost:8000";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
await p.goto(`${base}/#region`);
await p.waitForSelector(".hl-num", { timeout: 60000 });
await p.waitForTimeout(5000);
await p.screenshot({ path: "../docs/media/region-overview.png" });
await p.click("text=Rosa Parks → Juvisy");
await p.waitForSelector(".jverdict", { timeout: 60000 });
await p.waitForTimeout(3000);
await p.screenshot({ path: "../docs/media/region-journey.png" });
await p.getByRole("tab", { name: "Stale messages" }).click();
await p.locator(".right .rank button").first().click();
await p.waitForTimeout(3000);
await p.screenshot({ path: "../docs/media/region-stale.png" });
await b.close();
