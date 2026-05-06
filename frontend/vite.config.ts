import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const api = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Browser calls same-origin `/health` and `/v1/...` in dev; Vite forwards to the API.
      "/health": api,
      "/v1": api,
      "/docs": api,
      "/openapi.json": api,
      "/redoc": api,
    },
  },
});
