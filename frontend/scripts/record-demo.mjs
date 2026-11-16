// Records the UNLOCK demo by driving the real app (no mocked data) and logs segment start times
// so narration clips can be placed exactly. Usage: node video/record.mjs <outdir>
import { chromium } from "@playwright/test";
import { mkdirSync, writeFileSync, readdirSync, renameSync } from "node:fs";

const OUT = process.argv[2] || "video/out";
const BASE = process.env.BASE || "http://127.0.0.1:8000";
mkdirSync(OUT, { recursive: true });
// narration durations in seconds (Kokoro af_heart, video/narration.json)
import { readFileSync, existsSync } from "node:fs";
const DUR = { a1: 6.49, a2: 13.25, a3: 10.33, a4: 12.86, a5: 8.77, a6: 7.45, a7: 10.03, a8: 12.5, a9: 4.52 };
const CAP = {
  a1: "A station can be accessible. Its network may not be.",
  a2: "Paste an outage report → UNLOCK finds the exact lift in the Relate graph (station + platforms it SERVES). No guessing.",
  a3: "Simulated outage — published data untouched. Voies 50 & 51 cut off: 21 confirmed step-free connections lost.",
  a4: "The actual graph path: Voie 40 → ASC8 → souterrain nord → ASC3 → Voie 50. Two lifts in series.",
  a5: "Every repair in Île-de-France, ranked by connections restored — incl. lifts really out of service today.",
  a6: "With the repair: back to the published state. Independent Cypher query = engine.",
  a7: "Vague report? UNLOCK asks instead of guessing. 191 working lifts are single points of failure.",
  a8: "Same graph as a read-only MCP server: a real Claude Code session, replayed from its transcript.",
  a9: "",
};
const TRANSCRIPT = process.env.TRANSCRIPT || "";
const PAD = 0.9;

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1,
  recordVideo: { dir: OUT, size: { width: 1920, height: 1080 } } });
const page = await ctx.newPage();
const t0 = Date.now();
const marks = {};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await page.goto(`${BASE}/#station=Paris%20Gare%20du%20Nord`);
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


async function typeInto(locator, text) {
  await pointAt(locator); await locator.click();
  for (const ch of text) { await page.keyboard.type(ch); await sleep(28); }
}
await page.addStyleTag({ content: `
  #vterm { position: fixed; inset: 90px 140px 120px 140px; z-index: 58; background: #0d1526; color: #dfe6f2; border-radius: 12px;
    box-shadow: 0 30px 80px rgba(0,0,0,.45); padding: 22px 28px; font: 17px/1.5 "Atkinson Hyperlegible Next", sans-serif; overflow: hidden; }
  #vterm .hd { color: #8ea3c4; font-size: 14px; margin-bottom: 10px; }
  #vterm .u { color: #fff; font-weight: 700; margin: 6px 0 12px; }
  #vterm .t { color: #7fd1ae; font-family: ui-monospace, Consolas, monospace; font-size: 15px; margin: 3px 0; }
  #vterm .a { margin-top: 14px; white-space: pre-wrap; color: #fff; }
` });

await sleep(1200);
await seg("a1");
await page.evaluate(() => { document.getElementById("vcard").style.opacity = "0"; });
await seg("a2", async () => {
  await sleep(700);
  await page.evaluate(() => document.getElementById("vcard").remove());
  await typeInto(page.locator(".report textarea"), "Juvisy : ascenseur quai 50/51 HS depuis ce matin");
  await click(page.getByRole("button", { name: "Find the lift" }));
  await page.waitForSelector(".resolution");
  await pointAt(page.locator(".resolution .ev"));
});
await seg("a3", async () => {
  await click(page.getByRole("button", { name: "Simulate this outage" }));
  await page.waitForSelector(".banner.sim");
  await sleep(900);
  await pointAt(page.locator(".counts .c-CONFIRMED_ACCESSIBLE"));
  await sleep(2200);
  await pointAt(page.locator(".pair.changed").first());
});
await seg("a4", async () => {
  await click(page.locator(".pair").filter({ hasText: /Voie 40[^0-9]*Voie 50(?!\d)/ }).first());
  await page.waitForSelector(".evidence .chain .node");
  await pointAt(page.locator(".evidence .chain"));
});
await seg("a5", async () => {
  await click(page.locator(".evhead button"));
  await sleep(400);
  await pointAt(page.locator("button.cand").first());
  await sleep(2200);
  await pointAt(page.locator("button.cand").nth(1));
  await sleep(1000);
  await pointAt(page.locator("button.cand").nth(2));
});
await seg("a6", async () => {
  await click(page.locator("button.cand").first());
  await sleep(700);
  await pointAt(page.locator(".counts .c-CONFIRMED_ACCESSIBLE"));
  await sleep(1400);
  await pointAt(page.locator(".xcheck"));
});
await seg("a7", async () => {
  await click(page.locator(".chip").filter({ hasText: "Pontoise" }));
  await page.waitForSelector(".resolution .cands");
  await pointAt(page.locator(".resolution .cands"));
  await sleep(2600);
  await click(page.getByRole("tab", { name: "Lifts you can't lose" }));
  await pointAt(page.locator(".critical p").first());
});
await seg("a8", async () => {
  let lines = [];
  if (TRANSCRIPT && existsSync(TRANSCRIPT)) {
    const ev = readFileSync(TRANSCRIPT, "utf-8").split("\n").filter((l) => l.startsWith("{")).map((l) => JSON.parse(l));
    for (const e of ev) {
      if (e.type === "assistant") for (const c of (e.content || e.message?.content || [])) if (c.type === "tool_use" && c.name.startsWith("mcp__"))
        lines.push({ k: "t", s: `→ ${c.name.replace("mcp__unlock__", "unlock.")}(${JSON.stringify(c.input).slice(0, 90)})` });
      if (e.type === "result") lines.push({ k: "a", s: (e.result || "").replace(/\*\*/g, "") });
    }
  }
  const prompt = process.env.PROMPT || "";
  await page.evaluate(({ lines, prompt }) => {
    const t = document.createElement("div"); t.id = "vterm";
    t.innerHTML = `<div class="hd">claude -p … --mcp-config unlock (read-only Relate store) · real session, replayed</div><div class="u">› ${prompt}</div>`;
    document.body.appendChild(t);
    let i = 0;
    const step = () => { if (i >= lines.length) return; const d = document.createElement("div"); d.className = lines[i].k; d.textContent = lines[i].s; t.appendChild(d); i++; setTimeout(step, lines[i - 1].k === "t" ? 700 : 400); };
    setTimeout(step, 600);
  }, { lines, prompt });
});
await seg("a9", async () => {
  await caption("");
  await page.evaluate(() => {
    document.getElementById("vterm")?.remove();
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
