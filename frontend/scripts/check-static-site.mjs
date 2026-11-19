import { chromium } from "playwright";
// Smoke test of the built zero-install demo: serve ../site under /unlock-accessibility-graph/ (e.g. port 8090), then
// node scripts/check-static-site.mjs [url]
const url = process.argv[2] || "http://localhost:8090/unlock-accessibility-graph/";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
const errs = [];
p.on("console", (m) => { if (m.type() === "error") errs.push(m.text()); });
p.on("pageerror", (e) => errs.push(String(e)));
await p.goto(url);
await p.waitForSelector(".hl-num", { timeout: 60000 });
await p.waitForSelector('[data-relate="ready"], [data-relate="error"]', { timeout: 90000 });
console.log("banner:", (await p.locator(".static-banner").textContent()).slice(0, 400));
console.log("headline:", await p.locator(".hl-num").textContent());
await p.click("text=Rosa Parks → Juvisy");
await p.waitForSelector(".jverdict", { timeout: 60000 });
await p.waitForTimeout(1500);
console.log("journey:", (await p.locator(".jresult").textContent()).slice(0, 400));
await p.click("text=/^Watch Rosa Parks/");
await p.waitForSelector(".tw-list .tw-badge", { timeout: 30000 });
console.log("trip:", (await p.locator(".tw-list li").first().textContent()).slice(0, 300));
await p.getByRole("tab", { name: "Repairs that matter" }).click();
await p.locator(".right .rank button").nth(2).click();
await p.waitForSelector(".reach-num", { timeout: 60000 });
await p.waitForSelector("text=/Re-derived in Relate|disagrees/", { state: "attached", timeout: 60000 });   // inside "How do we know?"
console.log("reach:", (await p.locator(".reachbox").textContent()).slice(0, 500));

await p.selectOption(".regionpick select", "ara");
await p.waitForSelector(".hl-num", { timeout: 60000 });
await p.waitForTimeout(500);
console.log("ara headline:", await p.locator(".hl-num").textContent());
await p.click("text=Compare all regions");
await p.waitForSelector(".compare table", { timeout: 30000 });
console.log("compare rows:", await p.locator(".compare tbody tr").count());

console.log("errors:", errs.slice(0, 5));
await b.close();
