// Records the UNLOCK demo by driving the real app (no mocked data) and logs segment start times
// so narration clips can be placed exactly. Usage: node video/record.mjs <outdir>
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync, readdirSync, renameSync } from "node:fs";

const OUT = process.argv[2] || "video/out";
const BASE = process.env.BASE || "http://127.0.0.1:8000";
mkdirSync(OUT, { recursive: true });
// narration durations in seconds (Kokoro af_heart, video/narration.json)
const DUR = { s1: 6.49, s2: 14.57, s3: 9.54, s4: 9.94, s5: 14.68, s6: 11.99, s7: 9.58, s8: 6.70, s9: 4.52 };
const CAP = {
  s1: "A station can be accessible. Its network may not be.",
  s2: "401 SNCF stations in Île-de-France, one Relate graph file. Juvisy: 12 platforms joined to an underpass by lifts.",
  s3: "Lift ASC3 — Voies 50 et 51 / souterrain nord. 21 confirmed step-free connections can use it.",
  s4: "Simulated outage — published data untouched. 21 connections: confirmed → blocked.",
  s5: "The actual graph path: Voie 40 → ASC8 → souterrain nord → ASC3 → Voie 50. Two lifts in series.",
  s6: "Every repair in the region, ranked: ASC3 +21, then lifts really out of service today (+13, +13).",
  s7: "With the repair: back to the published state. Re-computed independently in Cypher — they agree.",
  s8: "One persistent Relate file: ~6,000 nodes, the path query, the statements it just ran.",
  s9: "",
};
const PAD = 0.9;

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1,
  recordVideo: { dir: OUT, size: { width: 1920, height: 1080 } } });
const page = await ctx.newPage();
const t0 = Date.now();
const marks = {};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await page.goto(`${BASE}/#station=Juvisy-sur-Orge`);
await page.waitForSelector(".section-svg");
await page.addStyleTag({ content: `
  #vcap { position: fixed; left: 50%; bottom: 34px; transform: translateX(-50%); max-width: 1180px; z-index: 50;
    background: rgba(20,33,61,.92); color: #fff; font: 600 23px/1.35 "Atkinson Hyperlegible Next", sans-serif;
    padding: 12px 22px; border-radius: 10px; text-align: center; transition: opacity .35s; }
  #vcap:empty { opacity: 0; }
  #vcard { position: fixed; inset: 0; z-index: 60; background: #14213d; color: #f3f5f7; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 22px; transition: opacity .7s; }
  #vcard h1 { font: 800 120px/1 "Archivo Variable", sans-serif; font-variation-settings: "wdth" 125; letter-spacing: .06em; margin: 0; }
  #vcard p { font: 400 34px/1.3 "Atkinson Hyperlegible Next", sans-serif; margin: 0; color: #b9c3d6; max-width: 1300px; text-align: center; }
  #vcard .big { font: 700 54px/1.25 "Archivo Variable", sans-serif; font-variation-settings: "wdth" 90; color: #fff; }
  #vcur { position: fixed; z-index: 55; width: 26px; height: 26px; border-radius: 50%; border: 3px solid #0f62fe;
    background: rgba(15,98,254,.18); pointer-events: none; transform: translate(-50%,-50%); left: 960px; top: 600px;
    transition: left .7s cubic-bezier(.3,.7,.3,1), top .7s cubic-bezier(.3,.7,.3,1); }
  #vcur.press { background: rgba(15,98,254,.55); }
` });
await page.evaluate(() => {
  const c = document.createElement("div"); c.id = "vcap"; document.body.appendChild(c);
  const k = document.createElement("div"); k.id = "vcard";
  k.innerHTML = `<p class="big">A station can be accessible.<br>Its network may not be.</p><h1>UNLOCK</h1><p>The Accessibility Impact Graph · built on Relate</p>`;
  document.body.appendChild(k);
  const u = document.createElement("div"); u.id = "vcur"; document.body.appendChild(u);
});
const caption = (t) => page.evaluate((t) => { document.getElementById("vcap").textContent = t; }, t);
async function pointAt(locator) {
  await locator.scrollIntoViewIfNeeded();
  const b = await locator.boundingBox();
  await page.evaluate(({ x, y }) => { const u = document.getElementById("vcur"); u.style.left = x + "px"; u.style.top = y + "px"; },
    { x: b.x + b.width / 2, y: b.y + b.height / 2 });
  await sleep(800);
}
async function click(locator) {
  await pointAt(locator);
  await page.evaluate(() => document.getElementById("vcur").classList.add("press"));
  await locator.click();
  await sleep(180);
  await page.evaluate(() => document.getElementById("vcur").classList.remove("press"));
}
async function seg(id, fn) {
  const start = Date.now();
  marks[id] = (start - t0) / 1000;
  await caption(CAP[id]);
  if (fn) await fn();
  const left = (DUR[id] + PAD) * 1000 - (Date.now() - start);
  if (left > 0) await sleep(left);
}

await sleep(1200);
await seg("s1");
await page.evaluate(() => { document.getElementById("vcard").style.opacity = "0"; });
await seg("s2", async () => {
  await sleep(900);
  await page.evaluate(() => document.getElementById("vcard").remove());
  await pointAt(page.locator(".map-wrap"));
  await sleep(3500);
  await pointAt(page.locator(".section-scroll"));
});
await seg("s3", async () => { await click(page.getByRole("button", { name: /Lift ASC\.PMR 4556 ASC3/ })); await sleep(600); await pointAt(page.locator(".deps")); });
await seg("s4", async () => {
  await click(page.getByRole("button", { name: "Simulate outage" }));
  await page.waitForSelector(".banner.sim");
  await sleep(700);
  await pointAt(page.locator(".counts .c-CONFIRMED_ACCESSIBLE"));
  await sleep(1800);
  await pointAt(page.locator(".pair.changed").first());
});
await seg("s5", async () => {
  await click(page.locator(".pair").filter({ hasText: /Voie 40[^0-9]*Voie 50(?!\d)/ }).first());
  await page.waitForSelector(".evidence .chain .node");
  await pointAt(page.locator(".evidence .chain"));
  await sleep(4000);
  await pointAt(page.locator(".evidence .stmts li").nth(3));
});
await seg("s6", async () => {
  await click(page.locator(".evhead button"));
  await sleep(500);
  await pointAt(page.locator("button.cand").first());
  await sleep(3000);
  await pointAt(page.locator("button.cand").nth(1));
  await sleep(1300);
  await pointAt(page.locator("button.cand").nth(2));
  await sleep(1300);
  await click(page.locator("button.cand").first());
});
await seg("s7", async () => {
  await sleep(600);
  await pointAt(page.locator(".counts .c-CONFIRMED_ACCESSIBLE"));
  await sleep(1500);
  await click(page.getByRole("tab", { name: "Simulated outage" }));
  await sleep(1300);
  await click(page.getByRole("tab", { name: "With proposed repair" }));
  await sleep(600);
  await pointAt(page.locator(".xcheck"));
});
await seg("s8", async () => {
  await click(page.getByRole("button", { name: "Inspect the graph" }));
  await sleep(1200);
  await page.evaluate(() => document.querySelector(".sheet").scrollTo({ top: 420, behavior: "smooth" }));
});
await seg("s9", async () => {
  await caption("");
  await page.evaluate(() => {
    const k = document.createElement("div"); k.id = "vcard"; k.style.opacity = "0";
    k.innerHTML = `<p class="big">UNLOCK doesn't just show you what's broken.<br>It shows you what fixing it makes possible.</p><h1>UNLOCK</h1><p>Find the repair that unlocks the most journeys.</p>`;
    document.body.appendChild(k); requestAnimationFrame(() => (k.style.opacity = "1"));
  });
});
await sleep(1500);
marks.end = (Date.now() - t0) / 1000;
const video = page.video();
await ctx.close();
const path = await video.path();
renameSync(path, `${OUT}/screen.webm`);
writeFileSync(`${OUT}/marks.json`, JSON.stringify(marks, null, 1));
await browser.close();
console.log(JSON.stringify(marks));
