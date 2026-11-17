import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // the zero-install demo build (scripts/build-static.mjs) publishes the exported snapshot + the Relate WASM engine
  publicDir: process.env.UNLOCK_PUBLIC_DIR || "public",
  server: { host: "127.0.0.1", port: 5173, proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { chunkSizeWarningLimit: 1500 },
});
