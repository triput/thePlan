import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/** Session-only synthetic stack for T2-REC-UI evidence. Proxies to isolated API, not :8000. */
const apiOrigin = process.env.SYNTHETIC_API_ORIGIN ?? "http://127.0.0.1:18081";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiOrigin,
        changeOrigin: true,
      },
    },
  },
});
