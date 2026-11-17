// Zero-install demo for GitHub Pages:  python scripts/export_static.py && node frontend/scripts/build-static.mjs
// Output: ../site (static files; region mode only; Relate runs in the browser as WebAssembly).
import { cpSync, existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { execSync } from "node:child_process";
import { resolve } from "node:path";

const base = process.env.UNLOCK_PAGES_BASE || "/unlock-accessibility-graph/";
const pub = resolve("static-public");
const data = resolve("static-data");
if (!existsSync(resolve(data, "regions.json"))) throw new Error("Run python scripts/export_static.py first");
rmSync(pub, { recursive: true, force: true });
mkdirSync(resolve(pub, "relate"), { recursive: true });
const wasm = resolve("node_modules/@relate/relate-wasm");
for (const f of ["relate.js", "relate_bg.wasm", "trap.js", "snippets"]) cpSync(resolve(wasm, f), resolve(pub, "relate", f), { recursive: true });
cpSync(resolve(wasm, "README.md"), resolve(pub, "relate", "README.md"));
writeFileSync(resolve(pub, "relate", "LICENSE.txt"), "@relate/relate-wasm 1.0.2 — Apache License 2.0 — https://github.com/relatedb/relate\n");
cpSync(data, resolve(pub, "data"), { recursive: true });
cpSync(resolve("public/favicon.svg"), resolve(pub, "favicon.svg"));
cpSync(resolve("public/og.png"), resolve(pub, "og.png"));
writeFileSync(resolve(pub, ".nojekyll"), "");
execSync(`npx vite build --base ${base} --outDir ../site --emptyOutDir`, {
  stdio: "inherit", env: { ...process.env, VITE_STATIC: "1", UNLOCK_PUBLIC_DIR: pub },
});
rmSync(pub, { recursive: true, force: true });
console.log("static demo → ../site");
