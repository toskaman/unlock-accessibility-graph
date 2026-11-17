// README screenshot of the zero-install demo's region comparison: node scripts/shot-static.mjs [url]
import { chromium } from "playwright";
const url = process.argv[2] || "http://localhost:8090/unlock-accessibility-graph/";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1600, height: 1000 } });
await p.goto(url);
await p.waitForSelector(".hl-num", { timeout: 60000 });
await p.waitForSelector("text=/running as WebAssembly/", { timeout: 90000 });
await p.click("text=Compare all regions");
await p.waitForSelector(".compare table", { timeout: 30000 });
await p.waitForTimeout(2500);
await p.screenshot({ path: "../docs/media/regions-compare.png" });
await b.close();
