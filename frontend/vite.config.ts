import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";
import cesium from "vite-plugin-cesium";

const host = process.env.TAURI_DEV_HOST;

// https://vite.dev/config/
export default defineConfig({
  plugins: [svelte(), (cesium as any)()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    host: host || false,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/static": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/generated-images": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
    },
  },
});
