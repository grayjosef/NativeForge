import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const api = "http://127.0.0.1:8000";

const apiProxy = {
  "/v1": api,
  "/docs": api,
  "/openapi.json": api,
  "/redoc": api,
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Browser calls same-origin `/health` and `/v1/...` in dev; Vite forwards to the API.
      "/health": api,
      ...apiProxy,
    },
  },
  preview: {
    // Stamped dist/health is the demo listener check; do not proxy to API.
    proxy: { ...apiProxy },
    // Cloudflare Tunnel forwards Host: nf-dev.mayhem-nc.dev to loopback preview.
    allowedHosts: ["nf-dev.mayhem-nc.dev"],
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/setupTests.ts",
    include: ["src/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
    },
  },
});
