// WCAG 2.1 AA scan (axe-core) + phone/desktop screenshots of the zero-install demo.
// node scripts/check-static-a11y.mjs [url] [outDir]   (add ?lang=fr to the url to scan the French interface)
import { chromium, devices } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync, writeFileSync } from "node:fs";

const url = process.argv[2] || "http://localhost:8090/unlock-accessibility-graph/";
const out = process.argv[3] || "/tmp/a11y";
const scheme = process.argv[4] === "dark" ? "dark" : "light";   // node check-static-a11y.mjs <url> <out> dark
mkdirSync(out, { recursive: true });
const b = await chromium.launch();
const report = {};
for (const [name, ctxOpts] of [["desktop", { viewport: { width: 1440, height: 900 } }], ["phone", { ...devices["iPhone 13"] }]]) {
  const ctx = await b.newContext({ ...ctxOpts, colorScheme: scheme });
  const p = await ctx.newPage();
  await p.goto(url);
  await p.waitForSelector(".hl-num", { timeout: 60000 });
  await p.waitForSelector('[data-relate="ready"], [data-relate="error"]', { timeout: 120000 });
  await p.waitForTimeout(2000);
  await p.screenshot({ path: `${out}/${name}-top.png`, fullPage: false });
  const scan = async (label) => {
    const r = await new AxeBuilder({ page: p }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).exclude(".maplibregl-canvas").analyze();
    report[`${name}:${label}`] = r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help, target: v.nodes.slice(0, 3).map((n) => n.target.join(" ")) }));
  };
  await scan("home");
  await p.getByRole("button", { name: "Rosa Parks → Juvisy" }).click();
  await p.waitForSelector(".jverdict", { timeout: 60000 });
  await p.getByRole("button", { name: /^(Watch|Suivre) Rosa Parks/ }).click();
  await p.getByRole("tab", { name: /^(History|Historique)$/ }).click();
  await p.waitForTimeout(1500);
  await scan("journey+history");
  await p.screenshot({ path: `${out}/${name}-full.png`, fullPage: true });
  await ctx.close();
}
await b.close();
writeFileSync(`${out}/axe.json`, JSON.stringify(report, null, 1));
for (const [k, v] of Object.entries(report)) console.log(k, v.length ? v.map((x) => `${x.id}(${x.impact},${x.nodes})`).join(" ") : "0 violations");
